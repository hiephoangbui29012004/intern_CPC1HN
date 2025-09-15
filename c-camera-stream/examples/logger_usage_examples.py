# Logger Configuration Examples
# This file shows different ways to use the reusable logger utility

from utils.logger_config import setup_logger, setup_app_logger, get_logger

# Example 1: Basic logger setup
logger = setup_logger("my_application")
logger.info("This is a basic log message")

# Example 2: Application logger with metadata
app_logger = setup_app_logger(
    app_name="camera_stream",
    service_name="motion_detection", 
    version="1.0.0",
    environment="production"
)
app_logger.info("Application started")

# Example 3: Logger with custom fields
custom_logger = setup_logger(
    name="data_processor",
    log_file="data_processor.log",
    custom_fields={
        "component": "video_analyzer",
        "instance_id": "analyzer_001",
        "region": "us-west-2"
    }
)
custom_logger.info("Processing video data", extra={"video_id": "vid_123", "duration": 120})

# Example 4: Getting an existing logger
existing_logger = get_logger("my_application")
existing_logger.warning("This uses the same logger instance")

# Example 5: Different projects using the same utility

# Web API project
api_logger = setup_app_logger(
    app_name="user_api",
    service_name="authentication",
    version="2.1.0",
    environment="staging"
)

# Data processing pipeline
pipeline_logger = setup_app_logger(
    app_name="data_pipeline", 
    service_name="etl_processor",
    version="1.5.2",
    environment="production"
)

# Machine learning model
ml_logger = setup_logger(
    name="ml_model",
    custom_fields={
        "model_name": "object_detection_v3",
        "model_version": "3.2.1",
        "gpu_enabled": True
    }
)

# Example log messages with context
api_logger.info("User authentication successful", extra={"user_id": "user_123", "ip": "192.168.1.1"})
pipeline_logger.error("Data validation failed", extra={"batch_id": "batch_456", "error_count": 5})
ml_logger.debug("Model inference completed", extra={"inference_time_ms": 45, "confidence": 0.95})
