# agentic-comm-automator/src/utils.py
import logging
import os
import json
import datetime
from dotenv import load_dotenv

# Load environment variables from the .env file in the project root
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def setup_logging(name, level=logging.INFO):
    """Sets up a logger for specific modules."""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    if not logger.handlers:  # Prevent adding multiple handlers if called multiple times
        ch = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        logger.propagate = False  # avoid printing every message twice via the root logger
    return logger


def get_env_variable(var_name):
    """Retrieves an environment variable, raising an error if not found."""
    value = os.getenv(var_name)
    if value is None or value.strip() == "":
        raise ValueError(f"Environment variable '{var_name}' not set. Please check your .env file or environment settings.")
    return value.strip()


def ensure_directory_exists(path):
    """Ensures that a directory exists, creating it if necessary."""
    try:
        os.makedirs(path, exist_ok=True)
        logging.debug(f"Directory ensured: {path}")
    except OSError as e:
        logging.error(f"Error creating directory {path}: {e}")
        raise


def log_audit_entry(audit_log_list, status, message, task_type="N/A", details=None):
    """Adds an entry to the audit log list."""
    log_entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "status": status,
        "task_type": task_type,
        "message": message,
        "details": details if details else {}
    }
    audit_log_list.append(log_entry)
    if status == "ERROR" or status == "CRITICAL":
        logging.error(f"AUDIT LOG - {status}: {message} | Task: {task_type}")
    else:
        logging.info(f"AUDIT LOG - {status}: {message} | Task: {task_type}")
