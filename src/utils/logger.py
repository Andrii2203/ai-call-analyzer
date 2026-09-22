import json
import logging
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """
    Custom formatter to output logs in a structured JSON format.
    """
    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "component": getattr(record, "component", "default"),
            "msg": record.getMessage(),
            "module": record.module,
            "func": record.funcName,
        }

        # Include additional fields if they are present in extra
        if record.args:
            if isinstance(record.args, dict):
                log_record.update(record.args)

        # Handle exception info if present
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_record, ensure_ascii=False)


def get_logger(name: str, component: str = "default") -> logging.Logger:
    """
    Configures and returns a logger with JSON formatting.
    """
    logger = logging.getLogger(name)
    
    # Avoid duplicate handlers if logger is already configured
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = JsonFormatter()
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        
    # Set component as a filter or attribute
    class ComponentFilter(logging.Filter):
        def filter(self, record):
            record.component = component
            return True

    logger.addFilter(ComponentFilter())
    
    return logger
