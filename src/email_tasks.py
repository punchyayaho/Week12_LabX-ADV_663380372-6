# agentic-comm-automator/src/email_tasks.py
import smtplib
import imaplib
import email
import email.utils
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.header import decode_header, Header
import os
from .utils import setup_logging, ensure_directory_exists

logger = setup_logging(__name__)


class EmailTasks:
    """
    Handles sending and receiving emails via SMTP and IMAP protocols.
    """
    def __init__(self, smtp_server, smtp_port, imap_server, sender_email, sender_password):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.imap_server = imap_server
        self.sender_email = sender_email
        self.sender_password = sender_password
        self._smtp_server = None  # Internal SMTP server object
        self._imap_mail = None  # Internal IMAP mail object
        logger.info(f"EmailTasks initialized for {sender_email}.")

    # --- SMTP (Sending) Methods ---
    def _connect_smtp(self):
        """Establishes and logs into the SMTP server."""
        if self._smtp_server:  # Already connected
            return True
        try:
            self._smtp_server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=30)
            self._smtp_server.starttls()  # Secure the connection
            self._smtp_server.login(self.sender_email, self.sender_password)
            logger.info("Successfully connected and logged into SMTP server.")
            return True
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed. Check email and app password. Error: {e}")
        except smtplib.SMTPConnectError as e:
            logger.error(f"SMTP connection failed. Check server address and port. Error: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during SMTP connect/login: {e}")
        self._smtp_server = None
        return False

    def _disconnect_smtp(self):
        """Disconnects from the SMTP server."""
        if self._smtp_server:
            try:
                self._smtp_server.quit()
                logger.info("Disconnected from SMTP server.")
            except Exception as e:
                logger.warning(f"Error during SMTP disconnection: {e}")
            finally:
                self._smtp_server = None

    def send_email(self, recipients, subject, body, attachments=None, is_html=False):
        """
        Sends an email with dynamic content and multiple attachments.
        :param recipients: Dictionary with lists for 'to', 'cc', 'bcc'.
        :return: True if email sent successfully, False otherwise.
        """
        to_recipients = recipients.get('to', [])
        cc_recipients = recipients.get('cc', [])
        bcc_recipients = recipients.get('bcc', [])  # BCC is not put in the headers
        all_recipients = list(dict.fromkeys(to_recipients + cc_recipients + bcc_recipients))
        if not all_recipients:
            logger.error("No recipients specified for email.")
            return False
        if not self._connect_smtp():
            return False

        msg = MIMEMultipart()
        msg['From'] = self.sender_email
        msg['Subject'] = Header(subject, 'utf-8')  # UTF-8 so Thai text works
        msg['To'] = ", ".join(to_recipients)
        if cc_recipients:
            msg['Cc'] = ", ".join(cc_recipients)
        msg.attach(MIMEText(body, 'html' if is_html else 'plain', 'utf-8'))

        for attachment_path in attachments or []:
            if not os.path.exists(attachment_path):
                logger.warning(f"Attachment file not found: {attachment_path}. Skipping.")
                continue
            try:
                with open(attachment_path, "rb") as f:
                    part = MIMEApplication(f.read(), Name=os.path.basename(attachment_path))
                part['Content-Disposition'] = f'attachment; filename="{os.path.basename(attachment_path)}"'
                msg.attach(part)
                logger.info(f"Attached file: {attachment_path}")
            except Exception as e:
                logger.error(f"Error attaching file {attachment_path}: {e}")

        try:
            self._smtp_server.send_message(msg, from_addr=self.sender_email, to_addrs=all_recipients)
            logger.info(f"Email sent successfully to {', '.join(to_recipients)} (CC: {', '.join(cc_recipients)}). Subject: '{subject}'.")
            return True
        except Exception as e:
            logger.error(f"Failed to send email. Error: {e}")
            return False
        finally:
            self._disconnect_smtp()

    # --- IMAP (Receiving) Methods ---
    def _connect_imap(self):
        """Establishes and logs into the IMAP server."""
        if self._imap_mail:  # Already connected
            return True
        try:
            self._imap_mail = imaplib.IMAP4_SSL(self.imap_server)
            self._imap_mail.login(self.sender_email, self.sender_password)
            logger.info("Successfully connected and logged into IMAP server.")
            return True
        except imaplib.IMAP4.error as e:
            logger.error(f"IMAP authentication failed. Check email and app password. Error: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during IMAP connect/login: {e}")
        self._imap_mail = None
        return False

    def _disconnect_imap(self):
        """Disconnects from the IMAP server."""
        if self._imap_mail:
            try:
                self._imap_mail.logout()
                logger.info("Disconnected from IMAP server.")
            except Exception as e:
                logger.warning(f"Error during IMAP disconnection: {e}")
            finally:
                self._imap_mail = None

    def search_emails(self, mailbox='INBOX', criteria='UNSEEN', from_sender=None, subject_contains=None):
        """
        Searches for emails based on criteria.
        :return: A list of email UIDs (real IMAP UIDs, stable across reconnects).
        """
        if not self._connect_imap():
            return []
        try:
            self._imap_mail.select(mailbox)
            search_query = [criteria]
            if from_sender:
                search_query.extend(['FROM', f'"{from_sender}"'])
            if subject_contains:
                search_query.extend(['SUBJECT', f'"{subject_contains}"'])
            status, email_ids = self._imap_mail.uid('search', None, *search_query)
            if status != 'OK':
                logger.error(f"IMAP search failed. Status: {status}")
                return []
            uids = email_ids[0].split()
            logger.info(f"Found {len(uids)} emails matching criteria in '{mailbox}'.")
            return uids
        except Exception as e:
            logger.error(f"Error searching emails: {e}")
            return []
        finally:
            self._disconnect_imap()

    def fetch_email_content(self, uid, mark_as_read=True, download_attachments_dir=None):
        """
        Fetches the content of a specific email by UID.
        Optionally marks as read and downloads attachments.
        :return: A dictionary containing email details or None.
        """
        if not self._connect_imap():
            return None
        try:
            self._imap_mail.select('INBOX')
            status, msg_data = self._imap_mail.uid('fetch', uid, '(RFC822)')
            if status != 'OK' or not msg_data or msg_data[0] is None:
                logger.error(f"Failed to fetch email UID {uid}. Status: {status}")
                return None
            msg = email.message_from_bytes(msg_data[0][1])
            sender = self._decode_header_part(msg['From'])
            sender_address = email.utils.parseaddr(sender)[1] or sender
            subject = self._decode_header_part(msg['Subject'])
            email_text_body = ""
            email_html_body = ""
            attachments_meta = []  # List of dicts: {'filename': 'name', 'filepath': 'path'}

            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                filename = part.get_filename()
                if "attachment" in content_disposition or (filename and part.get_content_maintype() != 'multipart'):
                    if filename and download_attachments_dir:
                        ensure_directory_exists(download_attachments_dir)
                        filepath = os.path.join(download_attachments_dir, filename)
                        try:
                            with open(filepath, "wb") as f:
                                f.write(part.get_payload(decode=True))
                            attachments_meta.append({'filename': filename, 'filepath': filepath})
                            logger.info(f"Downloaded attachment: {filepath}")
                        except Exception as e:
                            logger.error(f"Error downloading attachment {filename}: {e}")
                    elif filename:
                        attachments_meta.append({'filename': filename, 'filepath': None})
                elif content_type == "text/plain":
                    email_text_body += part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='replace')
                elif content_type == "text/html":
                    email_html_body += part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='replace')

            if mark_as_read:
                self._imap_mail.uid('store', uid, '+FLAGS', '(\\Seen)')
                logger.info(f"Marked email UID {uid.decode('utf-8')} as read.")
            return {
                "uid": uid.decode('utf-8'),
                "sender": sender_address,
                "subject": subject,
                "text_body": email_text_body,
                "html_body": email_html_body,
                "has_attachments": bool(attachments_meta),
                "attachments_meta": attachments_meta,
            }
        except Exception as e:
            logger.error(f"Error fetching/parsing email UID {uid.decode('utf-8')}: {e}")
            return None
        finally:
            self._disconnect_imap()

    def _decode_header_part(self, header_value):
        """Decodes header parts that might be encoded (e.g., '=?UTF-8?B?U3ViamVjdA==?=')."""
        if header_value is None:
            return ""
        decoded_string = ""
        for part, charset in decode_header(header_value):
            if isinstance(part, bytes):
                try:
                    decoded_string += part.decode(charset if charset else 'utf-8')
                except Exception:
                    decoded_string += part.decode('latin-1', errors='replace')
            else:
                decoded_string += part
        return decoded_string.strip()
