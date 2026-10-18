# agentic-comm-automator/src/communication_agent.py
import os
import json
import datetime
import time
from .utils import setup_logging, log_audit_entry, ensure_directory_exists, get_env_variable
from .email_tasks import EmailTasks
from .sms_tasks import SMSTasks
from .template_renderer import TemplateRenderer

logger = setup_logging(__name__)


class CommunicationAgent:
    """
    An agent that orchestrates communication tasks (email, SMS) based on a
    structured configuration file, managing an internal context for dynamic values.
    """
    def __init__(self, config, base_dir):
        self.config = config
        self.audit_log = []
        self.context = {}  # Stores dynamic values for templating and task chaining
        self.start_time = datetime.datetime.now()
        self.base_dir = base_dir
        try:
            sender_email = get_env_variable("SENDER_EMAIL")
            sender_app_password = get_env_variable("SENDER_APP_PASSWORD").replace(" ", "")
            smtp_server = get_env_variable("SMTP_SERVER")
            smtp_port = int(get_env_variable("SMTP_PORT"))
            imap_server = get_env_variable("IMAP_SERVER")
            self.email_tasks = EmailTasks(smtp_server, smtp_port, imap_server, sender_email, sender_app_password)
            self.sms_tasks = SMSTasks(self.email_tasks)  # SMS uses EmailTasks for the underlying send
            self.template_renderer = TemplateRenderer()
            logger.info("CommunicationAgent initialized with task handlers.")
        except ValueError as e:
            logger.critical(f"Agent initialization failed: Missing environment variables. {e}")
            raise

    def _update_context(self, key, value):
        """Updates a value in the agent's context."""
        self.context[key] = value
        logger.debug(f"Context updated: '{key}' = {value}")

    def _render_template(self, template_string, extra=None):
        """Renders a template string using the current agent context (+ optional extra values)."""
        try:
            return self.template_renderer.render(template_string, {**self.context, **(extra or {})})
        except Exception as e:
            log_audit_entry(self.audit_log, "ERROR", f"Template rendering failed: {e}", "template_render", {"template": template_string})
            raise

    def _send_email_task(self, params):
        recipients = {k: [self._render_template(r) for r in v] for k, v in params.get('recipients', {}).items()}
        subject = self._render_template(params.get("subject_template"))
        body = self._render_template(params.get("body_template"))
        attachments = [os.path.join(self.base_dir, self._render_template(p)) for p in params.get("attachments", [])]
        ok = self.email_tasks.send_email(recipients, subject, body, attachments, params.get("is_html", False))
        return ok, ({"recipients": recipients, "subject": subject, "attachments": attachments} if ok else None)

    def _send_sms_task(self, params):
        phone_numbers = [self._render_template(p) for p in params.get("phone_numbers", [])]
        message = self._render_template(params.get("message_template"))
        carrier_name = self._render_template(params.get("carrier_name", ""))
        ok = self.sms_tasks.send_sms(phone_numbers, message, carrier_name)
        return ok, ({"phone_numbers": phone_numbers, "message": message} if ok else None)

    def _rule_matches(self, conditions, email_info):
        if "from_sender_is" in conditions and self._render_template(conditions["from_sender_is"]).lower() != email_info["sender"].lower():
            return False
        if "subject_contains" in conditions and self._render_template(conditions["subject_contains"]).lower() not in email_info["subject"].lower():
            return False
        if "body_contains" in conditions and self._render_template(conditions["body_contains"]).lower() not in email_info["text_body"].lower():
            return False
        if "has_attachments" in conditions and conditions["has_attachments"] != email_info["has_attachments"]:
            return False
        return True

    def _apply_actions(self, actions, email_info):
        applied = []
        if actions.get("send_sms_alert"):
            message = self._render_template(actions.get("alert_message_template", "Urgent email received: {subject} from {sender}"), email_info)
            numbers = [self._render_template(p) for p in actions.get("alert_phone_numbers", [])]
            carrier = self._render_template(actions.get("alert_carrier", ""))
            sent = self.sms_tasks.send_sms(numbers, message, carrier)
            applied.append(f"send_sms_alert ({'sent' if sent else 'not sent - carrier not supported'})")
        if "reply_with_template" in actions:
            reply_body = self._render_template(actions["reply_with_template"], email_info)
            reply_subject = self._render_template(actions.get("reply_subject_template", "Re: {subject}"), email_info)
            sent = self.email_tasks.send_email(recipients={'to': [email_info['sender']]}, subject=reply_subject, body=reply_body)
            applied.append(f"reply_with_template ({'sent' if sent else 'failed'})")
        return applied

    def _process_inbox_task(self, params):
        wait = params.get("wait_before_search_seconds", 0)
        if wait:
            logger.info(f"Waiting {wait} seconds for new emails to arrive...")
            time.sleep(wait)
        criteria = params.get("search_criteria", {})
        download_dir = os.path.join(self.base_dir, params.get("download_attachments_base_dir", "data/incoming_attachments"))
        uids = self.email_tasks.search_emails(
            mailbox=params.get("mailbox", "INBOX"),
            criteria=criteria.get("status", "UNSEEN"),
            from_sender=self._render_template(criteria["from_sender"]) if criteria.get("from_sender") else None,
            subject_contains=self._render_template(criteria["subject_contains"]) if criteria.get("subject_contains") else None,
        )
        processed = []
        if not uids:
            logger.info("No emails found matching search criteria for inbox processing.")
        for uid in uids:
            email_info = self.email_tasks.fetch_email_content(uid=uid, mark_as_read=True, download_attachments_dir=download_dir)
            if not email_info:
                logger.error(f"Failed to fetch content for email UID {uid.decode('utf-8')}.")
                continue
            logger.info(f"Processing email UID {email_info['uid']}: '{email_info['subject']}' from {email_info['sender']}")
            actions_done = []
            for i, rule in enumerate(params.get("rules", []), start=1):
                if self._rule_matches(rule.get("if", {}), email_info):
                    logger.info(f"Rule {i} matched for email UID {email_info['uid']}. Applying actions...")
                    actions_done += self._apply_actions(rule.get("then", {}), email_info)
                else:
                    logger.info(f"Rule {i} did not match for email UID {email_info['uid']}.")
            processed.append({"uid": email_info["uid"], "subject": email_info["subject"],
                              "attachments": [a["filepath"] for a in email_info["attachments_meta"]],
                              "actions": actions_done})
        return True, {"processed_emails": processed}

    def _process_task(self, task):
        """Dispatches a task to the appropriate handler and manages context."""
        task_type = task.get("type")
        task_name = task.get("name", task_type)
        params = task.get("parameters", {})
        output_context_key = task.get("output_context_key")
        logger.info(f"===== Executing task: '{task_name}' (Type: {task_type}) =====")
        log_audit_entry(self.audit_log, "INFO", f"Starting task '{task_name}'", task_type)
        try:
            if task_type == "send_email":
                success, output = self._send_email_task(params)
            elif task_type == "send_sms":
                success, output = self._send_sms_task(params)
            elif task_type == "process_inbox":
                success, output = self._process_inbox_task(params)
            else:
                log_audit_entry(self.audit_log, "WARNING", f"Unsupported task type: {task_type}", task_type)
                return
            if success and output is not None and output_context_key:
                self._update_context(output_context_key, output)
            if success:
                log_audit_entry(self.audit_log, "SUCCESS", f"Task '{task_name}' completed successfully.", task_type, output)
            else:
                status = "WARNING" if task_type == "send_sms" else "ERROR"
                log_audit_entry(self.audit_log, status, f"Task '{task_name}' did not complete.", task_type)
        except Exception as e:
            log_audit_entry(self.audit_log, "ERROR", f"An error occurred during task '{task_name}': {e}", task_type)
            logger.error(f"Error during task '{task_name}': {e}", exc_info=True)

    def _generate_audit_report(self, output_dir):
        """Generates a JSON audit report."""
        ensure_directory_exists(output_dir)
        report_path = os.path.join(output_dir, f"audit_report_comm_{datetime.datetime.now():%Y%m%d_%H%M%S}.json")
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(self.audit_log, f, indent=4, ensure_ascii=False, default=str)
            logger.info(f"Audit report saved to: {report_path}")
        except Exception as e:
            logger.error(f"Failed to save audit report: {e}")

    def run(self):
        """Executes all tasks defined in the configuration."""
        logger.info("Starting Communication Agent run...")
        log_audit_entry(self.audit_log, "INFO", "Communication Agent started.", "agent_run")
        # Simulated data that might come from previous agent runs (e.g., the Data Agent)
        self._update_context("report_name", "DailySalesSummary")
        self._update_context("report_date", datetime.date.today().strftime("%Y-%m-%d"))
        self._update_context("sales_figure", 12345.67)
        self._update_context("total_customers", 500)
        self._update_context("attachment_path_1", "data/reports/sales_report.pdf")
        self._update_context("attachment_path_2", "data/reports/summary_data.xlsx")
        # Student info from .env (shown in every email)
        self._update_context("student_name", os.getenv("STUDENT_NAME", "").strip())
        self._update_context("student_id", os.getenv("STUDENT_ID", "").strip())

        for task in self.config.get("tasks", []):
            self._process_task(task)

        duration = (datetime.datetime.now() - self.start_time).total_seconds()
        log_audit_entry(self.audit_log, "INFO", f"Communication Agent finished in {duration:.2f} seconds.", "agent_run_summary")
        logger.info(f"Communication Agent finished. Total time: {duration:.2f} seconds.")
        self._generate_audit_report(os.path.join(self.base_dir, 'reports'))
