import os
import logging

level = os.environ.get("LOG_LEVEL", "INFO").upper()

logging.basicConfig(level=level)
