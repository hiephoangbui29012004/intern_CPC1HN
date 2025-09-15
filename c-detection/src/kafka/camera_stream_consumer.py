import logging
import avro.schema
import avro.io
import io
import os
import time
from dotenv import load_dotenv
from confluent_kafka import Consumer, KafkaError, KafkaException
from typing import Optional, Dict, Any, Callable

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

ssl_ca_location = os.getenv('KAFKA_SSL_CA_LOCATION', './certs/ca.crt')
if not os.path.exists(ssl_ca_location):
    logger.warning(f"SSL CA certificate not found at {ssl_ca_location}")

# Kafka consumer configuration with SSL and SASL security
KAFKA_CONSUMER_CONFIG = {
    # The list of broker addresses the consumer will connect to.
    'bootstrap.servers': os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092'),
    
    # Consumer group ID
    'group.id': os.getenv('KAFKA_CONSUMER_GROUP_ID', 'camera-stream-consumer-group'),
    
    # --- Security Configuration for SASL/SSL ---
    'ssl.ca.location': ssl_ca_location,
    'security.protocol': os.getenv('KAFKA_SECURITY_PROTOCOL', 'SASL_SSL'),
    'sasl.mechanism': os.getenv('KAFKA_SASL_MECHANISM', 'SCRAM-SHA-256'),
    'sasl.username': os.getenv('KAFKA_SASL_USERNAME'),
    'sasl.password': os.getenv('KAFKA_SASL_PASSWORD'),
    
    # --- Consumer Configuration ---
    # Start reading from the beginning if no committed offset exists
    'auto.offset.reset': os.getenv('KAFKA_AUTO_OFFSET_RESET', 'earliest'),
    # Enable auto commit of offsets
    'enable.auto.commit': os.getenv('KAFKA_ENABLE_AUTO_COMMIT', 'false').lower() == 'true',
    # Auto commit interval (if auto commit is enabled)
    'auto.commit.interval.ms': int(os.getenv('KAFKA_AUTO_COMMIT_INTERVAL_MS', '5000')),
    # Session timeout
    'session.timeout.ms': int(os.getenv('KAFKA_SESSION_TIMEOUT_MS', '30000')),
    # Max poll interval
    'max.poll.interval.ms': int(os.getenv('KAFKA_MAX_POLL_INTERVAL_MS', '300000')),
    # Heartbeat interval
    'heartbeat.interval.ms': int(os.getenv('KAFKA_HEARTBEAT_INTERVAL_MS', '3000')),
}

# Avro schema for camera stream data (same as producer)
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
      "name": "compressed_image",
      "type": "bytes",
      "doc": "JPEG compressed image data in bytes"
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

def avro_deserializer(schema):
    """Create an Avro deserializer function for the given schema"""
    def deserialize(serialized_data):
        if serialized_data is None:
            return None
        bytes_reader = io.BytesIO(serialized_data)
        decoder = avro.io.BinaryDecoder(bytes_reader)
        reader = avro.io.DatumReader(schema)
        return reader.read(decoder)
    return deserialize

class CameraStreamConsumer:
    def __init__(self, topics=None, config=None, consumer_group_id=None):
        """
        Initialize Kafka consumer for camera stream with Avro deserialization
        
        Args:
            topics (list, optional): List of Kafka topics to subscribe to. 
                                   If None, uses CAMERA_STREAM_TOPIC from env
            config (dict, optional): Custom Kafka configuration. 
                                   If None, uses KAFKA_CONSUMER_CONFIG
            consumer_group_id (str, optional): Consumer group ID override
        """
        # Set topics
        if topics is None:
            default_topic = os.getenv('CAMERA_STREAM_TOPIC', 'camera-stream')
            self.topics = [default_topic]
        elif isinstance(topics, str):
            self.topics = [topics]
        else:
            self.topics = topics
        
        # Use provided config or default KAFKA_CONSUMER_CONFIG
        kafka_config = config if config is not None else KAFKA_CONSUMER_CONFIG.copy()
        
        # Override consumer group if provided
        if consumer_group_id:
            kafka_config['group.id'] = consumer_group_id
        
        # Initialize consumer
        self.consumer = Consumer(kafka_config)
        self.deserializer = avro_deserializer(CAMERA_STREAM_SCHEMA)
        self.running = False
        self._subscribed = False
        
        logger.info(f"Kafka consumer initialized for topics: {self.topics}")
        logger.info(f"Consumer group: {kafka_config.get('group.id')}")
        logger.info(f"Connected to broker: {kafka_config.get('bootstrap.servers')}")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures proper cleanup"""
        self.close()
    
    def subscribe(self, topics=None):
        """
        Subscribe to Kafka topics
        
        Args:
            topics (list, optional): Topics to subscribe to. If None, uses self.topics
        """
        topics_to_subscribe = topics or self.topics
        self.consumer.subscribe(topics_to_subscribe)
        self._subscribed = True
        logger.info(f"Subscribed to topics: {topics_to_subscribe}")
    
    def consume_message(self, timeout=1.0):
        """
        Consume a single message from Kafka
        
        Args:
            timeout (float): Timeout in seconds for polling
            
        Returns:
            dict: Deserialized message data or None if no message
        """
        try:
            msg = self.consumer.poll(timeout=timeout)
            
            if msg is None:
                return None
            
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    logger.debug(f"End of partition reached {msg.topic()}[{msg.partition()}] at offset {msg.offset()}")
                else:
                    logger.error(f"Consumer error: {msg.error()}")
                return None
            
            # Deserialize the message
            try:
                deserialized_data = self.deserializer(msg.value())
                
                # Add metadata to the message
                message_info = {
                    'data': deserialized_data,
                    'metadata': {
                        'topic': msg.topic(),
                        'partition': msg.partition(),
                        'offset': msg.offset(),
                        'key': msg.key().decode('utf-8') if msg.key() else None,
                        'timestamp': msg.timestamp(),
                        'headers': dict(msg.headers()) if msg.headers() else {}
                    }
                }
                
                logger.debug(f"Consumed message from {msg.topic()}[{msg.partition()}] at offset {msg.offset()}")
                return message_info
                
            except Exception as e:
                logger.error(f"Error deserializing message: {e}")
                return None
                
        except KafkaException as e:
            logger.error(f"Kafka exception while consuming: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error while consuming message: {e}")
            return None
    
    def commit_message(self, message_info=None, asynchronous=True):
        """
        Commit message offset
        
        Args:
            message_info (dict, optional): Message info returned by consume_message. 
                                         If None, commits current position
            asynchronous (bool): Whether to commit asynchronously
        """
        try:
            if message_info and 'metadata' in message_info:
                # Commit specific message offset
                metadata = message_info['metadata']
                from confluent_kafka import TopicPartition
                tp = TopicPartition(metadata['topic'], metadata['partition'], metadata['offset'] + 1)
                self.consumer.commit(offsets=[tp], asynchronous=asynchronous)
                logger.debug(f"Committed offset {metadata['offset'] + 1} for {metadata['topic']}[{metadata['partition']}]")
            else:
                # Commit current position
                self.consumer.commit(asynchronous=asynchronous)
                logger.debug("Committed current consumer position")
        except KafkaException as e:
            logger.error(f"Error committing offset: {e}")
        except Exception as e:
            logger.error(f"Unexpected error while committing offset: {e}")
    
    def consume_messages(self, message_handler: Callable[[Dict[str, Any]], bool], 
                        max_messages=None, timeout=1.0, auto_commit=False, 
                        max_retries=None, retry_delay=0.1):
        """
        Consume messages continuously with a custom handler
        
        Args:
            message_handler (callable): Function to handle each message. 
                                      Should return True to commit, False to skip commit
            max_messages (int, optional): Maximum number of messages to consume. 
                                        If None, consume indefinitely
            timeout (float): Timeout for each poll operation
            auto_commit (bool): Whether to automatically commit after successful processing
            max_retries (int, optional): Maximum retries for failed messages. None = infinite retries
            retry_delay (float): Delay between retries in seconds
        """
        self.running = True
        messages_consumed = 0
        current_message = None  # Hold current message for retries
        retry_count = 0
        
        try:
            # Subscribe to topics if not already subscribed
            if not self._subscribed:
                self.subscribe()
            
            logger.info("Starting message consumption...")
            
            while self.running:
                if max_messages and messages_consumed >= max_messages:
                    logger.info(f"Reached maximum message limit: {max_messages}")
                    break
                
                # Get new message only if we don't have a pending one
                if current_message is None:
                    current_message = self.consume_message(timeout=timeout)
                    retry_count = 0
                
                if current_message is None:
                    continue
                
                try:
                    # Process message with handler
                    should_commit = message_handler(current_message)
                    
                    # Commit if handler returned True or auto_commit is enabled
                    if should_commit or auto_commit:
                        self.commit_message(current_message)
                        logger.info("Message processed and committed successfully")
                    else:
                        logger.info("Message processed but not committed (handler returned False)")
                    
                    # Success - move to next message
                    current_message = None
                    retry_count = 0
                    messages_consumed += 1
                    
                except Exception as e:
                    retry_count += 1
                    logger.error(f"Error in message handler (attempt {retry_count}): {e}")
                    
                    # Check if we should continue retrying
                    if max_retries is not None and retry_count >= max_retries:
                        logger.error(f"Message failed after {max_retries} attempts, skipping...")
                        # Optionally commit to skip this problematic message
                        # self.commit_message(current_message)
                        current_message = None
                        retry_count = 0
                        continue
                    
                    # Wait before retry
                    if retry_delay > 0:
                        logger.info(f"Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                    
                    # Keep current_message for retry
                    continue
        
        except KeyboardInterrupt:
            logger.info("Consumer interrupted by user")
        except Exception as e:
            logger.error(f"Error in message consumption loop: {e}")
        finally:
            self.running = False
            logger.info(f"Message consumption stopped. Total messages consumed: {messages_consumed}")
    
    def stop(self):
        """Stop the consumer"""
        self.running = False
        logger.info("Consumer stop requested")
    
    def close(self):
        """Close the consumer connection"""
        self.running = False
        if hasattr(self, 'consumer') and self.consumer:
            self.consumer.close()
        logger.info("Kafka consumer closed")

# Export the consumer class
consumer = CameraStreamConsumer
