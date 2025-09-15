#!/usr/bin/env python3
"""
Test script to demonstrate the reusable logger functionality.
Run this script to verify the logger configuration works correctly.
"""

import os
import sys
import time
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from utils.logger_config import setup_app_logger, setup_logger

def test_basic_logger():
    """Test basic logger functionality."""
    print("Testing basic logger...")
    
    logger = setup_logger("test_basic")
    
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    
    print("✅ Basic logger test completed")

def test_app_logger():
    """Test application logger with metadata."""
    print("Testing application logger...")
    
    logger = setup_app_logger(
        app_name="test_app",
        service_name="test_service",
        version="1.0.0",
        environment="testing"
    )
    
    logger.info("Application started successfully")
    logger.info("Processing data", extra={
        'batch_id': 'batch_123',
        'record_count': 1500,
        'processing_time_ms': 2345
    })
    
    # Test error logging with exception
    try:
        raise ValueError("This is a test error")
    except Exception as e:
        logger.error("Test error occurred", extra={
            'error_type': type(e).__name__,
            'error_details': str(e)
        }, exc_info=True)
    
    print("✅ Application logger test completed")

def test_structured_logging():
    """Test structured logging capabilities."""
    print("Testing structured logging...")
    
    logger = setup_logger(
        "structured_test",
        custom_fields={
            'component': 'test_runner',
            'version': '2.0.0',
            'instance_id': 'test_001'
        }
    )
    
    # Test various data types in extra fields
    logger.info("Structured logging test", extra={
        'string_field': 'test_value',
        'integer_field': 42,
        'float_field': 3.14159,
        'boolean_field': True,
        'list_field': ['item1', 'item2', 'item3'],
        'dict_field': {'key1': 'value1', 'key2': 'value2'},
        'timestamp': int(time.time() * 1000)
    })
    
    print("✅ Structured logging test completed")

def test_multiple_loggers():
    """Test multiple logger instances."""
    print("Testing multiple loggers...")
    
    # Create different loggers for different components
    api_logger = setup_app_logger("api", "user_service", "1.0.0", "test")
    db_logger = setup_app_logger("database", "connection_pool", "2.1.0", "test")  
    cache_logger = setup_app_logger("cache", "redis_client", "3.0.0", "test")
    
    api_logger.info("API request received", extra={'endpoint': '/users', 'method': 'GET'})
    db_logger.info("Database query executed", extra={'query_time_ms': 45, 'rows': 12})
    cache_logger.info("Cache hit", extra={'key': 'user_123', 'ttl': 3600})
    
    print("✅ Multiple loggers test completed")

def check_log_files():
    """Check if log files were created."""
    print("Checking log files...")
    
    log_dir = os.getenv('LOG_DIRECTORY', './logs')
    
    if os.path.exists(log_dir):
        log_files = list(Path(log_dir).glob('*.log'))
        if log_files:
            print(f"✅ Found {len(log_files)} log files:")
            for log_file in log_files:
                size = log_file.stat().st_size
                print(f"  - {log_file.name} ({size} bytes)")
        else:
            print("⚠️  No log files found")
    else:
        print(f"⚠️  Log directory {log_dir} does not exist")

def main():
    """Run all tests."""
    print("🧪 Starting logger tests...\n")
    
    # Set test environment variables
    os.environ.setdefault('DEBUG_LEVEL', 'DEBUG')
    os.environ.setdefault('ENABLE_FILE_LOGGING', 'true')
    os.environ.setdefault('LOG_DIRECTORY', './test_logs')
    os.environ.setdefault('LOG_FORMAT', 'json')
    os.environ.setdefault('LOG_RETENTION_DAYS', '1')
    
    try:
        test_basic_logger()
        print()
        
        test_app_logger()
        print()
        
        test_structured_logging()
        print()
        
        test_multiple_loggers()
        print()
        
        check_log_files()
        print()
        
        print("🎉 All logger tests completed successfully!")
        print("\n📝 Check the test_logs directory for generated log files")
        print("💡 Try changing LOG_FORMAT to 'standard' to see human-readable logs")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
