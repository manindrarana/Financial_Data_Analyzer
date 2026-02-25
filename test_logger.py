from src.utils import get_logger

logger = get_logger("TestModule")

logger.debug("This is a debug message (You might not see this if LOG_LEVEL=INFO)")
logger.info("This is an info message (Standard output)")
logger.warning("This is a warning!")
logger.error("This is an error message!")