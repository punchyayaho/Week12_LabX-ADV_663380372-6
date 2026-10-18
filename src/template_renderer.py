# agentic-comm-automator/src/template_renderer.py
import os
import re
import string
from .utils import setup_logging

logger = setup_logging(__name__)

# ${ENV_VAR} placeholders (UPPER_CASE names) are filled from environment variables (.env)
ENV_PLACEHOLDER = re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}")


class TemplateRenderer:
    """
    A simple template renderer:
      1. ${ENV_VAR}  -> value from the environment (.env), e.g. ${SENDER_EMAIL}
      2. {key}       -> value from the agent context (str.format syntax, e.g. {sales_figure:.2f},
                        {attachments_meta[0][filepath]})
    """
    def render(self, template_string, context):
        if template_string is None:
            return ""

        def env_value(match):
            value = os.getenv(match.group(1))
            if value is None:
                raise ValueError(f"Environment variable '{match.group(1)}' used in template is not set.")
            return value.strip()

        try:
            text = ENV_PLACEHOLDER.sub(env_value, template_string)
            return string.Formatter().vformat(text, [], context)
        except KeyError as e:
            logger.error(f"Missing key in template context: {e}. Template: '{template_string}'")
            raise ValueError(f"Missing context key: {e}")
        except Exception as e:
            logger.error(f"Error rendering template: {e}. Template: '{template_string}'")
            raise
