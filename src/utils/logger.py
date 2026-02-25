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
