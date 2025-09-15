"""
Reusable logging configuration module for multiple projects.

This module provides a standardized logging setup with the following features:
- JSON structured logging for ELK stack compatibility
- Console logging with human-readable format
- Configurable file rotation and retention
- Environment variable configuration
- Custom fields support
- Multiple output formats (JSON, standard)

Usage:
    from utils.logger_config import setup_logger
    
    # Basic usage
    logger = setup_logger("my_app")
    
    # With custom configuration
    logger = setup_logger(
        name="my_app",
        log_file="my_app.log",
        custom_fields={"service": "my_service", "version": "1.0.0"}
    )
    
    # Using environment variables (recommended)
    logger = setup_logger("my_app")
"""

import json
import logging
import os
from logging.handlers import TimedRotatingFileHandler
from typing import Dict, Optional, Union
from datetime import datetime


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging compatible with ELK stack."""
    
    def __init__(self, custom_fields: Optional[Dict[str, Union[str, int, float]]] = None):
        """
        Initialize JSON formatter with optional custom fields.
        
        Args:
            custom_fields: Dictionary of custom fields to include in every log entry
        """
        super().__init__()
        self.custom_fields = custom_fields or {}
        
        # Standard fields that should be excluded from custom field extraction
        self.excluded_fields = {
            'name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
            'filename', 'module', 'lineno', 'funcName', 'created',
            'msecs', 'relativeCreated', 'thread', 'threadName',
            'processName', 'process', 'getMessage', 'exc_info',
            'exc_text', 'stack_info', 'taskName'
        }
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON string.
        
        Args:
            record: The log record to format
            
        Returns:
            JSON formatted log string
        """
        # Base log entry structure
        log_entry = {
            "@timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "thread": record.thread,
            "process": record.process
        }
        
        # Add custom fields
        log_entry.update(self.custom_fields)
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Add any extra fields from the log record
        for key, value in record.__dict__.items():
            if key not in self.excluded_fields and not key.startswith('_'):
                log_entry[key] = value
        
        return json.dumps(log_entry, ensure_ascii=False, default=str)


class LoggerConfig:
    """Configuration class for logger setup with environment variable support."""
    
    def __init__(self):
        """Initialize configuration from environment variables."""
        self.debug_mode = os.getenv('DEBUG_LEVEL', 'INFO').upper() == 'DEBUG'
        self.enable_file_logging = os.getenv('ENABLE_FILE_LOGGING', 'true').lower() == 'true'
        self.log_directory = os.getenv('LOG_DIRECTORY', './logs')
        self.log_retention_days = int(os.getenv('LOG_RETENTION_DAYS', '7'))
        self.console_log_level = os.getenv('CONSOLE_LOG_LEVEL', 'INFO').upper()
        self.file_log_level = os.getenv('FILE_LOG_LEVEL', 'DEBUG' if self.debug_mode else 'INFO').upper()
        self.log_format = os.getenv('LOG_FORMAT', 'json').lower()  # json or standard
        self.rotation_when = os.getenv('LOG_ROTATION_WHEN', 'midnight')
        self.rotation_interval = int(os.getenv('LOG_ROTATION_INTERVAL', '1'))


def setup_logger(
    name: str,
    log_file: Optional[str] = None,
    custom_fields: Optional[Dict[str, Union[str, int, float]]] = None,
    config: Optional[LoggerConfig] = None
) -> logging.Logger:
    """
    Set up a logger with JSON file logging and console output.
    
    Args:
        name: Logger name (usually the application/module name)
        log_file: Custom log file name (defaults to {name}.log)
        custom_fields: Dictionary of custom fields to include in all log entries
        config: Custom LoggerConfig instance (defaults to environment-based config)
    
    Returns:
        Configured logger instance
        
    Environment Variables:
        DEBUG_LEVEL: Set to 'DEBUG' to enable debug mode (default: 'INFO')
        ENABLE_FILE_LOGGING: Enable/disable file logging (default: 'true')
        LOG_DIRECTORY: Directory for log files (default: './logs')
        LOG_RETENTION_DAYS: Number of days to retain log files (default: '7')
        CONSOLE_LOG_LEVEL: Console logging level (default: 'INFO')
        FILE_LOG_LEVEL: File logging level (default: 'DEBUG' in debug mode, 'INFO' otherwise)
        LOG_FORMAT: Log format - 'json' or 'standard' (default: 'json')
        LOG_ROTATION_WHEN: When to rotate logs (default: 'midnight')
        LOG_ROTATION_INTERVAL: Rotation interval (default: '1')
    """
    # Use provided config or create from environment
    if config is None:
        config = LoggerConfig()
    
    # Get or create logger
    logger = logging.getLogger(name)
    
    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger
    
    # Set logger level
    logger.setLevel(logging.DEBUG if config.debug_mode else logging.INFO)
    
    # Setup file logging if enabled
    if config.enable_file_logging:
        success = _setup_file_logging(logger, name, log_file, custom_fields, config)
        if success:
            logger.info(f"📝 File logging enabled - Directory: {config.log_directory}, "
                       f"Retention: {config.log_retention_days} days, Format: {config.log_format}")
        else:
            logger.warning("⚠️ File logging setup failed, continuing with console logging only")
    else:
        logger.info("📝 File logging disabled via configuration")
    
    # Setup console logging
    _setup_console_logging(logger, config)
    
    return logger


def _setup_file_logging(
    logger: logging.Logger,
    name: str,
    log_file: Optional[str],
    custom_fields: Optional[Dict[str, Union[str, int, float]]],
    config: LoggerConfig
) -> bool:
    """
    Set up file logging with rotation.
    
    Returns:
        True if file logging was set up successfully, False otherwise
    """
    try:
        # Create log directory if it doesn't exist
        if not os.path.exists(config.log_directory):
            os.makedirs(config.log_directory, exist_ok=True)
            logger.info(f"📁 Created log directory: {config.log_directory}")
        
        # Determine log file name
        if log_file is None:
            log_file = f"{name}.log"
        
        log_file_path = os.path.join(config.log_directory, log_file)
        
        # Create rotating file handler
        file_handler = TimedRotatingFileHandler(
            log_file_path,
            when=config.rotation_when,
            interval=config.rotation_interval,
            backupCount=config.log_retention_days
        )
        
        # Set file handler level
        file_level = getattr(logging, config.file_log_level, logging.INFO)
        file_handler.setLevel(file_level)
        
        # Choose formatter based on configuration
        if config.log_format == 'json':
            formatter = JSONFormatter(custom_fields)
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
            )
        
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to set up file logging: {e}")
        return False


def _setup_console_logging(logger: logging.Logger, config: LoggerConfig) -> None:
    """Set up console logging with human-readable format."""
    console_handler = logging.StreamHandler()
    
    # Set console handler level
    console_level = getattr(logging, config.console_log_level, logging.INFO)
    console_handler.setLevel(console_level)
    
    # Use human-readable format for console
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    """
    Get an existing logger or create a new one with default configuration.
    
    Args:
        name: Logger name
        
    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        return setup_logger(name)
    return logger


# Convenience function for quick setup
def setup_app_logger(
    app_name: str,
    service_name: Optional[str] = None,
    version: Optional[str] = None,
    environment: Optional[str] = None
) -> logging.Logger:
    """
    Set up application logger with common fields.
    
    Args:
        app_name: Application name
        service_name: Service name (optional)
        version: Application version (optional)
        environment: Environment (dev, staging, prod, etc.) (optional)
        
    Returns:
        Configured logger
    """
    custom_fields = {"application": app_name}
    
    if service_name:
        custom_fields["service"] = service_name
    if version:
        custom_fields["version"] = version
    if environment:
        custom_fields["environment"] = environment
    
    return setup_logger(app_name, custom_fields=custom_fields)
