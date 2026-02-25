import logging
import os
import sys
from dotenv import load_dotenv

load_dotenv()

def get_logger(name: str) -> logging.Logger:
    """
    Creates a logger for code.
    Args:
        name (str): The name of module (use __name__)
    Returns:
        logging.Logger: A logger you can use to print messages
    """
    logger = logging.getLogger(name)

    level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_str, logging.INFO)
    logger.setLevel(level)

    if not logger.handlers:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)

        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] [%(name)s]: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(formatter)

        logger.addHandler(console_handler)

    return logger