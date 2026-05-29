"""
logging_config.py
-----------------
Centralized structured logging configuration for consistent logging across the platform.

Features:
- Structured JSON logging for log aggregation
- Contextual logging with request IDs
- Performance logging for slow operations
- Separate log files for different components
"""

import logging
import logging.config
import json
import os
from datetime import datetime
from typing import Optional, Any, Dict
import sys


# Ensure logs directory exists
LOGS_DIR = os.getenv("LOGS_DIR", "logs")
os.makedirs(LOGS_DIR, exist_ok=True)


class StructuredFormatter(logging.Formatter):
    """Custom formatter that outputs structured JSON logs."""
    
    def __init__(self, service_name: str = "lineage-platform"):
        self.service_name = service_name
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "service": self.service_name,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line_number": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
            log_entry["exception_type"] = record.exc_info[0].__name__
        
        # Add extra fields if present
        if hasattr(record, "extra_data"):
            log_entry["extra"] = record.extra_data
        
        # Add request ID if present
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        # Add performance timing if present
        if hasattr(record, "elapsed_ms"):
            log_entry["elapsed_ms"] = record.elapsed_ms
        
        return json.dumps(log_entry)


class ContextFilter(logging.Filter):
    """Filter that adds contextual information to log records."""
    
    def __init__(self, request_id: Optional[str] = None):
        super().__init__()
        self.request_id = request_id
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Add request ID to log record."""
        if self.request_id:
            record.request_id = self.request_id
        return True


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Get a configured logger instance.
    
    Parameters
    ----------
    name : str
        Logger name (typically __name__)
    level : int
        Logging level (default: INFO)
    
    Returns
    -------
    logging.Logger
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Only add handlers if not already configured
    if not logger.handlers:
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_formatter = StructuredFormatter()
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        
        # File handler
        log_file = os.path.join(LOGS_DIR, f"{name.replace('.', '_')}.log")
        try:
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(level)
            file_handler.setFormatter(console_formatter)
            logger.addHandler(file_handler)
        except (IOError, OSError) as e:
            logger.warning(f"Could not create file handler for {log_file}: {e}")
    
    return logger


def setup_logging(log_level: str = "INFO") -> None:
    """
    Configure logging for the entire application.
    
    Parameters
    ----------
    log_level : str
        Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler with structured formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(StructuredFormatter())
    root_logger.addHandler(console_handler)
    
    # Application file handler
    try:
        app_log_file = os.path.join(LOGS_DIR, "application.log")
        app_handler = logging.FileHandler(app_log_file)
        app_handler.setLevel(level)
        app_handler.setFormatter(StructuredFormatter())
        root_logger.addHandler(app_handler)
    except (IOError, OSError) as e:
        console_handler.emit(
            logging.LogRecord(
                "logging_config", logging.WARNING,
                "", 0, f"Could not create application log file: {e}", (), None
            )
        )
    
    # Error file handler (only ERROR and CRITICAL)
    try:
        error_log_file = os.path.join(LOGS_DIR, "error.log")
        error_handler = logging.FileHandler(error_log_file)
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(StructuredFormatter())
        root_logger.addHandler(error_handler)
    except (IOError, OSError):
        pass


class LogContextManager:
    """Context manager for adding request-scoped logging context."""
    
    def __init__(self, request_id: str, logger: logging.Logger, **context):
        self.request_id = request_id
        self.logger = logger
        self.context = context
        self.extra_filter = None
    
    def __enter__(self):
        """Enter context and add request ID to logger."""
        self.extra_filter = ContextFilter(self.request_id)
        self.logger.addFilter(self.extra_filter)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context and remove request ID filter."""
        if self.extra_filter:
            self.logger.removeFilter(self.extra_filter)
    
    def log_with_context(self, level: int, message: str, **extra) -> None:
        """Log a message with additional context."""
        context_data = {**self.context, **extra}
        
        record = logging.LogRecord(
            name=self.logger.name,
            level=level,
            pathname="",
            lineno=0,
            msg=message,
            args=(),
            exc_info=None,
        )
        record.extra_data = context_data
        record.request_id = self.request_id
        self.logger.handle(record)


class PerformanceLogger:
    """Context manager for logging operation performance."""
    
    def __init__(self, logger: logging.Logger, operation: str, threshold_ms: int = 1000):
        self.logger = logger
        self.operation = operation
        self.threshold_ms = threshold_ms
        self.start_time = None
    
    def __enter__(self):
        """Enter context and record start time."""
        import time
        self.start_time = time.time()
        self.logger.debug(f"Starting operation: {self.operation}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context and log performance metrics."""
        import time
        elapsed_ms = (time.time() - self.start_time) * 1000
        
        if exc_type:
            self.logger.error(
                f"Operation '{self.operation}' failed after {elapsed_ms:.2f}ms: {exc_val}",
                exc_info=(exc_type, exc_val, exc_tb)
            )
        elif elapsed_ms > self.threshold_ms:
            self.logger.warning(
                f"Slow operation: '{self.operation}' took {elapsed_ms:.2f}ms (threshold: {self.threshold_ms}ms)"
            )
        else:
            self.logger.debug(f"Operation '{self.operation}' completed in {elapsed_ms:.2f}ms")


# Initialize logging on module load
def _initialize_logging():
    """Initialize logging configuration."""
    log_level = os.getenv("LOG_LEVEL", "INFO")
    setup_logging(log_level)


_initialize_logging()
