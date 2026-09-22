import functools
import random
import time
from typing import Any, Callable, Tuple, Type

from src.utils.logger import get_logger

logger = get_logger(__name__, component="RETRY")

def exponential_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
) -> Callable:
    """
    Decorator for exponential backoff retry logic.
    
    Args:
        max_retries: Maximum number of retry attempts.
        initial_delay: Initial delay between retries in seconds.
        backoff_factor: Factor by which the delay increases each retry.
        jitter: If True, adds randomness to the delay to avoid thundering herd problem.
        exceptions: Tuple of exceptions to catch and retry.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            retries = 0
            delay = initial_delay
            
            while True:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    retries += 1
                    func_name = getattr(func, "__name__", str(func))
                    if retries > max_retries:
                        logger.error(
                            f"Max retries ({max_retries}) reached for {func_name}. Error: {str(e)}"
                        )
                        raise e
                    
                    # Calculate wait time
                    wait_time = delay * (backoff_factor ** (retries - 1))
                    if jitter:
                        wait_time *= (1 + random.random() * 0.1)  # Add 0-10% jitter
                    
                    func_name = getattr(func, "__name__", str(func))
                    logger.warning(
                        f"Retry {retries}/{max_retries} for {func_name} after {wait_time:.2f}s. "
                        f"Caught exception: {e.__class__.__name__}: {str(e)}"
                    )
                    
                    time.sleep(wait_time)
                    
        return wrapper
    return decorator
