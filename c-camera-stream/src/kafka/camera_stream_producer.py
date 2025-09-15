import logging
import avro.schema
import avro.io
import io
import os
import time
from dotenv import load_dotenv
from confluent_kafka import Producer

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Validate required environment variables
required_env_vars = ['KAFKA_SASL_USERNAME', 'KAFKA_SASL_PASSWORD']
missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# Kafka configuration with SSL and SASL security - loaded from environment variables
KAFKA_CONFIG = {
    # The list of broker addresses the producer will connect to.
    'bootstrap.servers': os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092'),

    # --- Security Configuration for SASL/SSL ---
    # These settings are required to securely connect to the Kafka cluster.
    'ssl.ca.location': os.getenv('KAFKA_SSL_CA_LOCATION', './certs/ca.crt'), 
    'security.protocol': os.getenv('KAFKA_SECURITY_PROTOCOL', 'SASL_SSL'),
    'sasl.mechanism': os.getenv('KAFKA_SASL_MECHANISM', 'SCRAM-SHA-256'),
    'sasl.username': os.getenv('KAFKA_SASL_USERNAME'),
    'sasl.password': os.getenv('KAFKA_SASL_PASSWORD'),

    # Producer buffering and performance settings (confluent-kafka specific)
    'queue.buffering.max.kbytes': 131072,    # 128MB (128 * 1024 KB)
    'batch.size': 1572864,                   # 1.5MB
    'message.max.bytes': 2097152,            # 2MB
    'linger.ms': 10,
    'acks': '1',
    'retries': 5,
    'compression.type': 'snappy'
}

# Avro schema for camera stream data
CAMERA_STREAM_SCHEMA = avro.schema.parse("""
{
  "type": "record",
  "name": "CameraStream",
  "namespace": "camera.stream",
  "fields": [
    {
      "name": "camera_id",
      "type": "string",
      "doc": "Unique identifier for the camera"
    },
    {
      "name": "image_path",
      "type": "string",
      "doc": "Path to the image file"
    },
    {
      "name": "timestamp",
      "type": "long",
      "doc": "Unix timestamp when motion was detected"
    },
    {
      "name": "motion_area",
      "type": "float",
      "doc": "Total area of motion detected in pixels"
    },
    {
      "name": "frame_dimensions",
      "type": {
        "type": "record",
        "name": "Dimensions",
        "fields": [
          { "name": "width", "type": "int" },
          { "name": "height", "type": "int" }
        ]
      },
      "doc": "Frame width and height"
    },
    {
      "name": "compression_quality",
      "type": "int",
      "doc": "JPEG compression quality (0-100)"
    },
    {
      "name": "original_size",
      "type": "long",
      "doc": "Original image size in bytes before compression"
    },
    {
      "name": "compressed_size",
      "type": "long",
      "doc": "Compressed image size in bytes"
    }
  ]
}
""")

def avro_serializer(schema):
    """Create an Avro serializer function for the given schema"""
    def serialize(obj):
        writer = avro.io.DatumWriter(schema)
        bytes_writer = io.BytesIO()
        encoder = avro.io.BinaryEncoder(bytes_writer)
        writer.write(obj, encoder)
        return bytes_writer.getvalue()
    return serialize

class KafkaBufferException(Exception):
    """Custom exception for Kafka buffer errors"""
    pass

class CameraStreamProducer:
    def __init__(self, topic=None, config=None):
        """
        Initialize Kafka producer for camera stream with Avro serialization
        
        Args:
            topic (str, optional): Kafka topic name. If None, uses CAMERA_STREAM_TOPIC from env
            config (dict, optional): Custom Kafka configuration. If None, uses KAFKA_CONFIG
        """
        self.topic = topic or os.getenv('CAMERA_STREAM_TOPIC', 'camera-stream')
        
        # Use provided config or default KAFKA_CONFIG
        kafka_config = config if config is not None else KAFKA_CONFIG.copy()
        
        # Initialize producer with the configuration (confluent_kafka doesn't use serializers in config)
        self.producer = Producer(kafka_config)
        
        # Buffer error tracking
        self.buffer_error_start_time = None
        self.buffer_error_threshold_seconds = int(os.getenv('KAFKA_BUFFER_ERROR_THRESHOLD_SECONDS', '60'))
        self.consecutive_buffer_errors = 0
        
        logger.info(f"Kafka producer initialized with Avro serialization for topic: {self.topic}")
        logger.info(f"Connected to broker: {kafka_config.get('bootstrap.servers', 'default')}")
    
    def _check_buffer_errors(self, exception=None):
        """
        Check for buffer errors and track timing
        Raises KafkaBufferException if buffer errors persist for more than threshold
        """
        current_time = time.time()
        
        # Check if current exception is a buffer error
        is_buffer_error = False
        if exception:
            error_msg = str(exception).lower()
            is_buffer_error = any(keyword in error_msg for keyword in [
                'buffer', 'memory', 'queue full', 'producer queue is full'
            ])
        
        if is_buffer_error:
            self.consecutive_buffer_errors += 1
            
            # Start tracking time on first buffer error
            if self.buffer_error_start_time is None:
                self.buffer_error_start_time = current_time
                logger.warning(f"🟡 Kafka buffer error detected. Starting timer. Error: {exception}")
            else:
                # Check if buffer errors have persisted beyond threshold
                error_duration = current_time - self.buffer_error_start_time
                if error_duration >= self.buffer_error_threshold_seconds:
                    error_msg = (f"Kafka buffer errors persisted for {error_duration:.1f} seconds "
                               f"(threshold: {self.buffer_error_threshold_seconds}s). "
                               f"Consecutive errors: {self.consecutive_buffer_errors}")
                    logger.error(f"🔴 {error_msg}")
                    raise KafkaBufferException(error_msg)
                else:
                    logger.warning(f"🟡 Kafka buffer error ongoing for {error_duration:.1f}s. "
                                 f"Consecutive errors: {self.consecutive_buffer_errors}")
        else:
            # Reset tracking on successful operation
            if self.buffer_error_start_time is not None:
                error_duration = current_time - self.buffer_error_start_time
                logger.info(f"✅ Kafka buffer errors resolved after {error_duration:.1f}s. "
                          f"Total consecutive errors: {self.consecutive_buffer_errors}")
            
            self.buffer_error_start_time = None
            self.consecutive_buffer_errors = 0
    
    def send_frame(self, frame_data, key=None):
        """
        Send camera stream data to Kafka topic
        
        Args:
            frame_data (dict): Camera stream data to send (must match Avro schema)
            key (str, optional): Message key for partitioning
        
        Returns:
            Future: Kafka send result future
        """
        try:
            # Validate required fields for CameraStream schema
            required_fields = [
                'camera_id', 'timestamp', 'motion_area',
                'frame_dimensions', 'compression_quality', 'original_size', 'compressed_size'
            ]
            for field in required_fields:
                if field not in frame_data:
                    raise ValueError(f"Missing required field: {field}")
            
            # Validate field types
            if not isinstance(frame_data['timestamp'], int):
                frame_data['timestamp'] = int(frame_data['timestamp'])
            
            if not isinstance(frame_data['motion_area'], float):
                frame_data['motion_area'] = float(frame_data['motion_area'])
            
            # Validate frame_dimensions structure
            if 'frame_dimensions' in frame_data:
                dims = frame_data['frame_dimensions']
                if not isinstance(dims, dict) or 'width' not in dims or 'height' not in dims:
                    raise ValueError("frame_dimensions must be a dict with 'width' and 'height' fields")
                if not isinstance(dims['width'], int):
                    dims['width'] = int(dims['width'])
                if not isinstance(dims['height'], int):
                    dims['height'] = int(dims['height'])
            
            # Validate integer fields
            int_fields = ['compression_quality', 'original_size', 'compressed_size']
            for field in int_fields:
                if not isinstance(frame_data[field], int):
                    frame_data[field] = int(frame_data[field])
            
            # Serialize the data using Avro
            serialized_value = avro_serializer(CAMERA_STREAM_SCHEMA)(frame_data)
            serialized_key = frame_data['camera_id'].encode('utf-8') if key is None else str(key).encode('utf-8')
            
            # Send to Kafka using confluent_kafka API
            self.producer.produce(self.topic, value=serialized_value, key=serialized_key)
            logger.debug(f"Sent camera stream data to topic: {self.topic} - key: {serialized_key}")
            
            # Check for successful send (no buffer errors)
            self._check_buffer_errors()
            
            # Return None since confluent_kafka doesn't return futures like kafka-python
            return None
        except Exception as e:
            # Check if this is a buffer error and track it
            self._check_buffer_errors(e)
            logger.error(f"Error sending camera stream data: {e}")
            raise
    
    def send_message(self, message, key=None):
        """
        Send camera stream message to Kafka topic
        
        Args:
            message (dict): Camera stream message data (must conform to CameraStream schema)
            key (str, optional): Message key for partitioning
        
        Returns:
            None: confluent_kafka doesn't return futures like kafka-python
        """
        try:
            # Message must match the CameraStream schema
            # If it doesn't have the required fields, this will fail during serialization
            logger.debug("Sending message with Avro serialization")
            
            # Serialize the data using Avro
            serialized_value = avro_serializer(CAMERA_STREAM_SCHEMA)(message)
            serialized_key = str(key).encode('utf-8') if key else None
            
            # Send to Kafka using confluent_kafka API
            self.producer.produce(self.topic, value=serialized_value, key=serialized_key)
            logger.debug(f"Sent message to topic: {self.topic}")
            
            # Check for successful send (no buffer errors)
            self._check_buffer_errors()
            
            return None
        except Exception as e:
            # Check if this is a buffer error and track it
            self._check_buffer_errors(e)
            logger.error(f"Error sending message: {e}")
            raise
    
    def flush(self):
        """Flush any pending messages"""
        self.producer.flush()
    
    def close(self):
        """Close the producer connection"""
        # confluent_kafka uses flush() to wait for messages to be delivered before closing
        self.producer.flush()
        logger.info("Kafka producer closed")

# Export the producer class
producer = CameraStreamProducer