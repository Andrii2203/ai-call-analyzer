import pytest
import time
from unittest.mock import MagicMock
from src.utils.retry import exponential_backoff

def test_exponential_backoff_success():
    mock_func = MagicMock(return_value="success")
    decorator = exponential_backoff(max_retries=3, initial_delay=0.1)
    decorated_func = decorator(mock_func)
    
    result = decorated_func()
    
    assert result == "success"
    assert mock_func.call_count == 1

def test_exponential_backoff_retry_then_success():
    mock_func = MagicMock()
    mock_func.side_effect = [ValueError("Error"), "success"]
    
    decorator = exponential_backoff(max_retries=3, initial_delay=0.1, jitter=False)
    decorated_func = decorator(mock_func)
    
    start_time = time.time()
    result = decorated_func()
    end_time = time.time()
    
    assert result == "success"
    assert mock_func.call_count == 2
    # Delay for first retry is initial_delay = 0.1s
    assert end_time - start_time >= 0.1

def test_exponential_backoff_max_retries_reached():
    mock_func = MagicMock(side_effect=ValueError("Persistent Error"))
    
    decorator = exponential_backoff(max_retries=2, initial_delay=0.01)
    decorated_func = decorator(mock_func)
    
    with pytest.raises(ValueError, match="Persistent Error"):
        decorated_func()
    
    # 1 initial call + 2 retries = 3 total calls
    assert mock_func.call_count == 3
