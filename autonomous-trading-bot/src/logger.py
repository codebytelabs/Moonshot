"""
Structured logging with loguru.
- stderr: INFO level, human-readable
- File: DEBUG level, JSON-structured, 10MB rotation, 14-day retention
- Separate error log for critical issues
"""
import sys
import os
from loguru import logger


def setup_logging(log_dir: str = "logs", debug: bool = False) -> "logger":
    """Configure and return the loguru logger."""
    os.makedirs(log_dir, exist_ok=True)

    # Remove default handler
    logger.remove()

    # Console: human-readable
    console_level = "DEBUG" if debug else "INFO"
    logger.add(
        sys.stderr,
        level=console_level,
        format=(
            "<green>{time:HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    # Main log file: JSON-structured for machine parsing
    logger.add(
        os.path.join(log_dir, "bot.log"),
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
        rotation="10 MB",
        retention="14 days",
        compression="gz",
        serialize=True,  # JSON output
    )

    # Error-only log file
    logger.add(
        os.path.join(log_dir, "errors.log"),
        level="ERROR",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {name}:{function}:{line} | {message}",
        rotation="5 MB",
        retention="30 days",
        compression="gz",
    )

    logger.info("Logging initialized", log_dir=log_dir, console_level=console_level)
    return logger
