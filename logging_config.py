"""
Logging configuration for the Discord bot.
Uses loguru for structured logging with file rotation and console output.
"""
import sys
from pathlib import Path

from loguru import logger

from config import settings


def setup_logging() -> None:
    """Configure application logging."""
    # Remove default handler
    logger.remove()

    # Console handler with colorized output
    logger.add(
        sys.stdout,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        level=settings.log_level,
        colorize=True,
    )

    # File handler with rotation
    log_path = Path(settings.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger.add(
        log_path,
        format=(
            "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
            "{name}:{function}:{line} | {message}"
        ),
        level=settings.log_level,
        rotation="10 MB",
        retention="7 days",
        compression="zip",
        encoding="utf-8",
    )

    # Suppress discord.py debug logs unless DEBUG level
    if settings.log_level != "DEBUG":
        logger.disable("discord")
        logger.disable("discord.http")
        logger.disable("discord.gateway")
        logger.disable("discord.client")
        logger.disable("discord.webhook")
        logger.disable("aiohttp")


def get_logger(name: str):
    """Get a logger instance for a module."""
    return logger.bind(module=name)