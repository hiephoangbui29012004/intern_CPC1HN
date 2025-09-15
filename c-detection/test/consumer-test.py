import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.kafka.camera_stream_consumer import CameraStreamConsumer
import logging
from datetime import datetime
from typing import Dict, Any
from time import sleep


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create outputs directory if it doesn't exist
OUTPUTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'outputs')
os.makedirs(OUTPUTS_DIR, exist_ok=True)

# Example message handler function
def default_message_handler(message_info: Dict[str, Any]) -> bool:
    """
    Default message handler that logs message details and saves images
    
    Args:
        message_info: Message info containing data and metadata
        
    Returns:
        bool: True to commit the message, False to skip commit
    """
    try:
        data = message_info['data']
        metadata = message_info['metadata']
        
        logger.info(f"📸 Received camera stream from {data['camera_id']}")
        logger.info(f"   Timestamp: {data['timestamp']}")
        logger.info(f"   Motion area: {data['motion_area']:.2f} pixels")
        logger.info(f"   Frame size: {data['frame_dimensions']['width']}x{data['frame_dimensions']['height']}")
        logger.info(f"   Compression: {data['compression_quality']}% quality")
        logger.info(f"   Size: {data['compressed_size']} bytes (was {data['original_size']} bytes)")
        logger.info(f"   Topic: {metadata['topic']}, Partition: {metadata['partition']}, Offset: {metadata['offset']}")
        
        # Save the image to outputs folder
        if 'compressed_image' in data and data['compressed_image']:
            try:
                # Create filename with timestamp and camera ID
                timestamp = datetime.fromtimestamp(data['timestamp'] / 1000)  # Convert from milliseconds
                filename = f"{data['camera_id']}_{timestamp.strftime('%Y%m%d_%H%M%S_%f')[:-3]}.jpg"
                filepath = os.path.join(OUTPUTS_DIR, filename)
                
                # Write the compressed image data to file
                with open(filepath, 'wb') as f:
                    f.write(data['compressed_image'])
                
                logger.info(f"💾 Image saved: {filename}")
                
            except Exception as e:
                logger.error(f"Error saving image: {e}")
        
        # Return True to commit the message
        return True
        
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        return False

if __name__ == "__main__":
    camera_consumer = CameraStreamConsumer()
    
    try:
        # Start consuming messages with default handler
        camera_consumer.consume_messages(
            message_handler=default_message_handler,
            auto_commit=False,
            retry_delay=3
        )
    except KeyboardInterrupt:
        logger.info("Shutting down consumer...")
    finally:
        camera_consumer.close()