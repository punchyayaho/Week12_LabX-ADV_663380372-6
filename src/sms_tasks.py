# agentic-comm-automator/src/sms_tasks.py
from .utils import setup_logging
from .email_tasks import EmailTasks  # Reuse EmailTasks for sending actual email

logger = setup_logging(__name__)


class SMSTasks:
    """
    Provides a simplified interface to send SMS via email-to-SMS gateways.
    Relies on EmailTasks for the actual email transmission.
    NOTE: Thai carriers (AIS / TrueMove H / dtac) have no public email-to-SMS gateway,
    so SMS is skipped with a warning for them.
    """
    def __init__(self, email_tasks_instance):
        if not isinstance(email_tasks_instance, EmailTasks):
            raise TypeError("SMSTasks requires an instance of EmailTasks.")
        self.email_tasks = email_tasks_instance
        # Common US carrier email-to-SMS gateways (add more as needed)
        self.carrier_gateways = {
            "att": "@txt.att.net",
            "verizon": "@vtext.com",
            "tmobile": "@tmomail.net",
            "sprint": "@messaging.sprintpcs.com",
            "boost": "@sms.boostmobile.com",
            "cricket": "@mms.cricketwireless.net",
            "us_cellular": "@email.uscc.net",
        }
        logger.info("SMSTasks initialized.")

    def send_sms(self, phone_numbers, message, carrier_name=None):
        """
        Sends SMS messages via email-to-SMS gateway for multiple recipients.
        :return: True if all messages were sent (email-wise), False otherwise.
        """
        success_count = 0
        total_attempts = 0
        for phone_number in phone_numbers:
            total_attempts += 1
            if carrier_name and carrier_name.lower() in self.carrier_gateways:
                sms_gateway_address = f"{phone_number}{self.carrier_gateways[carrier_name.lower()]}"
            elif '@' in phone_number and '.' in phone_number:  # already a full gateway address
                sms_gateway_address = phone_number
            else:
                logger.warning(f"Carrier '{carrier_name}' has no known email-to-SMS gateway for {phone_number}. Cannot send SMS.")
                continue
            logger.info(f"Attempting to send SMS to {phone_number} via gateway: {sms_gateway_address}")
            if self.email_tasks.send_email(recipients={'to': [sms_gateway_address]}, subject="", body=message):
                success_count += 1
        if total_attempts > 0:
            logger.info(f"Attempted to send {total_attempts} SMS messages, {success_count} succeeded (email-wise).")
            return success_count == total_attempts
        return False
