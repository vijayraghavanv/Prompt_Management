# app/core/logging.py
import sys
from pathlib import Path
from loguru import logger
from .config import get_settings

settings = get_settings()


class LoggerManager:
    @staticmethod
    def setup_logging():
        # Remove default logger
        logger.remove()

        # Ensure log directory exists
        log_path = Path(settings.LOG_PATH)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Add file logger
        logger.add(
            settings.LOG_PATH,
            level=settings.LOG_LEVEL,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message} | {extra}",
            rotation="500 MB",
            retention="10 days"
        )

        # Add console logger for development
        if settings.APP_ENV == "development":
            logger.add(
                sys.stdout,
                level=settings.LOG_LEVEL,
                format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | <cyan>{message}</cyan>"
            )


logger_manager = LoggerManager()