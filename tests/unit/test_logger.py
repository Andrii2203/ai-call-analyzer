import io
import json
import logging

from src.utils.logger import JsonFormatter, get_logger


def test_json_logger_output():
    # Setup a logger with a string buffer
    logger = get_logger("test_logger", component="TEST")
    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)

    # Log something
    test_msg = "Test message"
    logger.info(test_msg)

    # Verify JSON structure
    output = log_capture.getvalue().strip().split('\n')
    log_json = json.loads(output[-1])

    assert log_json["msg"] == test_msg
    assert log_json["level"] == "INFO"
    assert log_json["component"] == "TEST"
    assert "timestamp" in log_json
    assert "module" in log_json
