# agentic-comm-automator/main.py
import os
import sys

# Make sure the project root is on the path so the 'src' package can be imported
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from src.config_parser import ConfigParser
from src.communication_agent import CommunicationAgent
from src.utils import setup_logging, ensure_directory_exists

logger = setup_logging(__name__)


def check_required_files(config, base_dir):
    """Checks that all attachment files referenced in send_email tasks exist."""
    missing = []
    for task in config['tasks']:
        if task['type'] == 'send_email':
            for att in task.get('parameters', {}).get('attachments', []):
                path = os.path.join(base_dir, att)
                if '{' not in att and not os.path.exists(path):
                    missing.append(path)
    return (not missing), missing


def main():
    """Main entry point for the Agentic Communication Automator."""
    config_file_path = os.path.join(BASE_DIR, 'configs', 'comm_pipeline_config.json')
    try:
        for d in ['data', os.path.join('data', 'reports'), os.path.join('data', 'incoming_attachments'), 'reports']:
            ensure_directory_exists(os.path.join(BASE_DIR, d))

        logger.info(f"Loading configuration from: {config_file_path}")
        config = ConfigParser(config_file_path).load_config()

        files_exist, missing = check_required_files(config, BASE_DIR)
        if not files_exist:
            logger.critical(f"Missing attachment files: {', '.join(missing)}. Run 'python create_sample_files.py'.")
            sys.exit(1)

        logger.info("Initializing Communication Agent...")
        agent = CommunicationAgent(config, BASE_DIR)
        logger.info("Running Communication Agent workflow...")
        agent.run()
        logger.info("Communication automation process completed.")
    except FileNotFoundError as e:
        logger.critical(f"File system error: {e}")
    except ValueError as e:
        logger.critical(f"Configuration or environment variable error: {e}")
        logger.info("Please check your config file and .env.")
    except Exception as e:
        logger.critical(f"An unexpected critical error occurred during execution: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
