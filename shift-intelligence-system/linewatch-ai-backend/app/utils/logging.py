"""Structured logging configuration using loguru."""
import sys
from loguru import logger


def setup_logging(level: str = "INFO"):
    """Configure loguru logger with colored output and structured format."""
    
    # Remove default handler
    logger.remove()
    
    # Add custom handler with colors and agent context
    logger.add(
        sys.stdout,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{extra[agent]}</cyan> | "
            "<level>{message}</level>"
        ),
        level=level,
        colorize=True,
    )
    
    return logger


def get_agent_logger(agent_name: str):
    """Get a logger instance bound to a specific agent."""
    return logger.bind(agent=agent_name)
