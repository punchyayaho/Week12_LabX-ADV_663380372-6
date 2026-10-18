# agentic-comm-automator/src/config_parser.py
import json
import os
from .utils import setup_logging

logger = setup_logging(__name__)


class ConfigParser:
    """
    Parses and validates the communication automation configuration from a JSON file.
    """
    def __init__(self, config_path):
        self.config_path = config_path
        self.config = {}

    def load_config(self):
        """Loads the configuration from the specified JSON file."""
        if not os.path.exists(self.config_path):
            logger.critical(f"Configuration file not found: {self.config_path}")
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except json.JSONDecodeError as e:
            logger.critical(f"Invalid JSON format in config file: {e}")
            raise ValueError(f"Invalid JSON format in config file: {e}")
        self._validate_config()
        logger.info(f"Configuration loaded successfully from {self.config_path}")
        return self.config

    def _validate_config(self):
        """
        Validates the loaded configuration to ensure required fields and task structures are present.
        """
        if "tasks" not in self.config:
            raise ValueError("Missing required field in config: 'tasks'")
        if not isinstance(self.config["tasks"], list):
            raise ValueError("Config field 'tasks' must be a list.")
        for i, task in enumerate(self.config["tasks"]):
            if "type" not in task:
                raise ValueError(f"Task {i} is missing 'type' field.")
            if "name" not in task:
                raise ValueError(f"Task {i} (type: {task['type']}) is missing 'name' field.")
            params = task.get("parameters")
            if task["type"] == "send_email":
                # recipients.to is a list inside 'recipients' (matches the config format)
                if not params or not all(k in params for k in ["recipients", "subject_template", "body_template"]):
                    raise ValueError(f"Task {i} (send_email) requires 'recipients', 'subject_template', 'body_template' in parameters.")
                if not isinstance(params["recipients"].get("to"), list):
                    raise ValueError(f"Task {i} (send_email) 'recipients.to' must be a list.")
                if "attachments" in params and not isinstance(params["attachments"], list):
                    raise ValueError(f"Task {i} (send_email) 'attachments' parameter must be a list.")
            elif task["type"] == "send_sms":
                if not params or not all(k in params for k in ["phone_numbers", "message_template"]):
                    raise ValueError(f"Task {i} (send_sms) requires 'phone_numbers', 'message_template' in parameters.")
                if not isinstance(params["phone_numbers"], list):
                    raise ValueError(f"Task {i} (send_sms) 'phone_numbers' parameter must be a list.")
            elif task["type"] == "process_inbox":
                if not params or "search_criteria" not in params:
                    raise ValueError(f"Task {i} (process_inbox) requires 'search_criteria' in parameters.")
                if "rules" in params and not isinstance(params["rules"], list):
                    raise ValueError(f"Task {i} (process_inbox) 'rules' parameter must be a list.")
        logger.info("Configuration validated.")
