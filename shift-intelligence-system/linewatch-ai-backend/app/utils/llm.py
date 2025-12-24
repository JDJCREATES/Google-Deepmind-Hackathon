import asyncio
import random
from functools import wraps
from typing import Any, Callable, TypeVar

from app.utils.logging import get_agent_logger

logger = get_agent_logger("LLMUtils")

T = TypeVar("T")

def with_retry(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 10.0,
    backoff_factor: float = 2.0,
    jitter: bool = True
):
    """
    Decorator for async functions to retry on exceptions with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts.
        initial_delay: Initial delay format in seconds.
        max_delay: Maximum delay in seconds.
        backoff_factor: Multiplier for delay after each failure.
        jitter: Whether to add random jitter to delay.
    """
    def decorator(func: Callable[..., Any]):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    is_resource_exhausted = "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)
                    
                    if attempt == max_retries:
                        logger.error(f"❌ Operation failed after {max_retries} retries: {e}")
                        raise last_exception
                    
                    # Calculate delay
                    current_delay = delay
                    if jitter:
                        current_delay *= (0.5 + random.random())
                    
                    # Log retry
                    level = "WARNING" if is_resource_exhausted else "INFO"
                    msg = f"⚠️ Retry {attempt + 1}/{max_retries} for {func.__name__} due to {type(e).__name__}. Waiting {current_delay:.2f}s..."
                    if is_resource_exhausted:
                        msg += " (Quota Exceeded)"
                        
                    if level == "WARNING":
                        logger.warning(msg)
                    else:
                        logger.info(msg)
                    
                    await asyncio.sleep(current_delay)
                    
                    # Update delay for next iteration
                    delay = min(delay * backoff_factor, max_delay)
            
            raise last_exception
        return wrapper
    return decorator
