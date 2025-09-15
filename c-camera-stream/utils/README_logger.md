# Reusable Logger Configuration

This module provides a standardized, reusable logging configuration that can be used across multiple Python projects. It supports structured JSON logging, console output, file rotation, and is fully configurable via environment variables.

## Features

- **Structured Logging**: JSON format compatible with ELK stack (Elasticsearch, Logstash, Kibana)
- **Multiple Output Formats**: JSON for structured logging or standard format for human readability
- **File Rotation**: Daily log rotation with configurable retention
- **Environment Configuration**: Full configuration via environment variables
- **Custom Fields**: Add custom metadata to all log entries
- **Thread-Safe**: Safe for use in multi-threaded applications
- **Flexible Setup**: Multiple setup functions for different use cases

## Quick Start

### Basic Usage

```python
from utils.logger_config import setup_logger

# Simple logger setup
logger = setup_logger("my_app")
logger.info("Application started")
```

### Application Logger with Metadata

```python
from utils.logger_config import setup_app_logger

# Logger with application metadata
logger = setup_app_logger(
    app_name="camera_stream",
    service_name="motion_detection",
    version="1.0.0",
    environment="production"
)
logger.info("Motion detected", extra={"camera_id": "cam_01", "motion_area": 1500})
```

## Configuration

### Environment Variables

All configuration is done via environment variables:

| Variable                | Default        | Description                         |
| ----------------------- | -------------- | ----------------------------------- |
| `DEBUG_LEVEL`           | `INFO`         | Set to `DEBUG` to enable debug mode |
| `ENABLE_FILE_LOGGING`   | `true`         | Enable/disable file logging         |
| `LOG_DIRECTORY`         | `./logs`       | Directory for log files             |
| `LOG_RETENTION_DAYS`    | `7`            | Number of days to retain log files  |
| `CONSOLE_LOG_LEVEL`     | `INFO`         | Console logging level               |
| `FILE_LOG_LEVEL`        | `DEBUG`/`INFO` | File logging level                  |
| `LOG_FORMAT`            | `json`         | Log format (`json` or `standard`)   |
| `LOG_ROTATION_WHEN`     | `midnight`     | When to rotate logs                 |
| `LOG_ROTATION_INTERVAL` | `1`            | Rotation interval                   |

### Example .env File

```bash
# Debug mode
DEBUG_LEVEL=INFO

# File logging
ENABLE_FILE_LOGGING=true
LOG_DIRECTORY=./logs
LOG_RETENTION_DAYS=7

# Log levels
CONSOLE_LOG_LEVEL=INFO
FILE_LOG_LEVEL=DEBUG

# Format and rotation
LOG_FORMAT=json
LOG_ROTATION_WHEN=midnight
LOG_ROTATION_INTERVAL=1

# Application metadata
APP_VERSION=1.0.0
ENVIRONMENT=production
```

## API Reference

### Functions

#### `setup_logger(name, log_file=None, custom_fields=None, config=None)`

Set up a logger with file and console output.

**Parameters:**

- `name` (str): Logger name
- `log_file` (str, optional): Custom log file name
- `custom_fields` (dict, optional): Custom fields to include in all log entries
- `config` (LoggerConfig, optional): Custom configuration object

**Returns:** `logging.Logger`

#### `setup_app_logger(app_name, service_name=None, version=None, environment=None)`

Set up application logger with common metadata fields.

**Parameters:**

- `app_name` (str): Application name
- `service_name` (str, optional): Service name
- `version` (str, optional): Application version
- `environment` (str, optional): Environment (dev, staging, prod)

**Returns:** `logging.Logger`

#### `get_logger(name)`

Get an existing logger or create a new one with default configuration.

**Parameters:**

- `name` (str): Logger name

**Returns:** `logging.Logger`

## Usage Examples

### Different Project Types

#### Web API

```python
from utils.logger_config import setup_app_logger

logger = setup_app_logger(
    app_name="user_api",
    service_name="authentication",
    version="2.1.0",
    environment="production"
)

logger.info("User login", extra={"user_id": "user_123", "ip": "192.168.1.1"})
```

#### Data Pipeline

```python
from utils.logger_config import setup_app_logger

logger = setup_app_logger(
    app_name="data_pipeline",
    service_name="etl_processor",
    version="1.5.2",
    environment="production"
)

logger.error("Processing failed", extra={"batch_id": "batch_456", "error_count": 5})
```

#### Machine Learning Model

```python
from utils.logger_config import setup_logger

logger = setup_logger(
    name="ml_model",
    custom_fields={
        "model_name": "object_detection_v3",
        "model_version": "3.2.1",
        "gpu_enabled": True
    }
)

logger.info("Inference completed", extra={"inference_time_ms": 45, "confidence": 0.95})
```

### Custom Configuration

```python
from utils.logger_config import setup_logger, LoggerConfig

# Create custom configuration
config = LoggerConfig()
config.log_directory = "/custom/logs"
config.log_retention_days = 30
config.log_format = "standard"

logger = setup_logger("custom_app", config=config)
```

## Log Output Examples

### JSON Format (default)

```json
{
  "@timestamp": "2025-01-15T10:30:45.123456",
  "level": "INFO",
  "logger": "camera_stream",
  "message": "Motion detected",
  "module": "main",
  "function": "detect_motion",
  "line": 245,
  "thread": 140234567,
  "process": 12345,
  "application": "camera_stream",
  "service": "motion_detection",
  "version": "1.0.0",
  "environment": "production",
  "camera_id": "cam_01",
  "motion_area": 1500
}
```

### Standard Format

```
2025-01-15 10:30:45,123 - camera_stream - INFO - Motion detected
```

## Integration with Different Projects

### 1. Copy the Logger Module

Copy `utils/logger_config.py` to your project's utils directory.

### 2. Install Dependencies

```bash
pip install python-dotenv  # If using .env files
```

### 3. Update Imports

```python
from utils.logger_config import setup_app_logger
```

### 4. Configure Environment

Set environment variables or create a `.env` file with your configuration.

### 5. Initialize Logger

```python
logger = setup_app_logger("your_app_name")
```

## Best Practices

1. **Use application logger** for main applications with metadata
2. **Use setup_logger** for libraries and utilities
3. **Add context** with `extra` parameter for important log messages
4. **Use appropriate log levels**: DEBUG for development, INFO for production events, WARNING for issues, ERROR for failures
5. **Include custom fields** for application-specific metadata
6. **Configure via environment** for different deployment environments

## Benefits of This Approach

1. **Consistency**: Same logging format across all projects
2. **Flexibility**: Configurable via environment variables
3. **Scalability**: JSON format works well with log aggregation systems
4. **Maintainability**: Single source of truth for logging configuration
5. **Reusability**: Drop-in replacement for any Python project
6. **Production-Ready**: Built-in rotation, retention, and error handling
