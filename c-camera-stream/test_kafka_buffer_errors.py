#!/usr/bin/env python3
"""
Test script để simulate Kafka buffer errors
Dùng để test mechanism restart container
"""

import os
import sys
import time
import logging
from dotenv import load_dotenv

# Add src to path để import được
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from kafka.camera_stream_producer import CameraStreamProducer, KafkaBufferException

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_buffer_error_simulation():
    """Test Kafka buffer error simulation"""
    
    # Override threshold for testing (30 seconds)
    os.environ['KAFKA_BUFFER_ERROR_THRESHOLD_SECONDS'] = '30'
    
    # Create producer
    producer = CameraStreamProducer()
    
    # Simulate buffer errors
    logger.info("🧪 Starting buffer error simulation test...")
    logger.info(f"Buffer error threshold: {producer.buffer_error_threshold_seconds} seconds")
    
    try:
        for i in range(50):  # Simulate many errors
            try:
                # Simulate a buffer error
                fake_error = Exception("producer queue is full - simulated error")
                producer._check_buffer_errors(fake_error)
                
                logger.info(f"Iteration {i+1}: Simulated buffer error")
                time.sleep(1)  # Wait 1 second between errors
                
            except KafkaBufferException as e:
                logger.error(f"🔴 KafkaBufferException caught after {i+1} iterations!")
                logger.error(f"Error: {e}")
                # In real application, this would cause sys.exit(1)
                logger.info("✅ Test completed - buffer error threshold mechanism working!")
                return True
                
    except Exception as e:
        logger.error(f"Unexpected error during test: {e}")
        return False
    
    logger.warning("⚠️ Test did not trigger KafkaBufferException - check threshold settings")
    return False

def test_buffer_error_recovery():
    """Test buffer error recovery mechanism"""
    
    # Override threshold for testing
    os.environ['KAFKA_BUFFER_ERROR_THRESHOLD_SECONDS'] = '10'
    
    # Create producer
    producer = CameraStreamProducer()
    
    logger.info("🧪 Starting buffer error recovery test...")
    
    # Simulate some buffer errors
    for i in range(5):
        fake_error = Exception("producer queue is full - simulated error")
        producer._check_buffer_errors(fake_error)
        time.sleep(1)
    
    logger.info("📊 Buffer errors simulated, now testing recovery...")
    
    # Simulate successful operation (no error)
    producer._check_buffer_errors()
    
    # Check if recovery was logged
    if producer.buffer_error_start_time is None and producer.consecutive_buffer_errors == 0:
        logger.info("✅ Recovery test passed - error tracking reset!")
        return True
    else:
        logger.error("❌ Recovery test failed - error tracking not reset")
        return False

if __name__ == "__main__":
    logger.info("🚀 Starting Kafka buffer error tests...")
    
    # Test 1: Buffer error simulation
    test1_result = test_buffer_error_simulation()
    
    # Wait between tests
    time.sleep(2)
    
    # Test 2: Buffer error recovery
    test2_result = test_buffer_error_recovery()
    
    # Summary
    logger.info("📋 Test Summary:")
    logger.info(f"  - Buffer error threshold test: {'✅ PASS' if test1_result else '❌ FAIL'}")
    logger.info(f"  - Buffer error recovery test: {'✅ PASS' if test2_result else '❌ FAIL'}")
    
    if test1_result and test2_result:
        logger.info("🎉 All tests passed!")
        sys.exit(0)
    else:
        logger.error("💥 Some tests failed!")
        sys.exit(1)
