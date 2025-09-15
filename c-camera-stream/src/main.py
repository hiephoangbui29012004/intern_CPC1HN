import json
import time
import cv2
import os
import sys
import numpy as np
from dotenv import load_dotenv
from kafka.camera_stream_producer import producer, KafkaBufferException
from PIL import Image
from collections import deque
import io
import threading
import queue
import logging
from utils.logger_config import setup_app_logger
from utils.minio_service import create_minio_client, MinioService

# Load environment variables from .env file
load_dotenv()

# Get configuration from environment variables
CAMERA_ID = os.getenv('CAMERA_ID') 
CAMERA_URL = os.getenv('RTSP_CAMERA_URL')
MOTION_THRESHOLD = int(os.getenv('MOTION_THRESHOLD', '500')) 
MIN_CONTOUR_AREA = int(os.getenv('MIN_CONTOUR_AREA', '100'))
BLUR_SIZE = int(os.getenv('BLUR_SIZE', '21'))
DEBUG_MODE = os.getenv('DEBUG_LEVEL', 'INFO').upper() == 'DEBUG'
CHECK_INTERVAL = int(os.getenv('INTERVAL_SECONDS', '5')) 
COMPRESSION_QUALITY = int(os.getenv('COMPRESS_IMAGE_QUALITY', '80'))

# Logging configuration - now using reusable logger utility
ENABLE_FILE_LOGGING = os.getenv('ENABLE_FILE_LOGGING', 'true').lower() == 'true'
LOG_DIRECTORY = os.getenv('LOG_DIRECTORY', '/app/logs')
LOG_RETENTION_DAYS = int(os.getenv('LOG_RETENTION_DAYS', '3'))

# Kafka buffer monitoring configuration
KAFKA_BUFFER_ERROR_THRESHOLD_SECONDS = int(os.getenv('KAFKA_BUFFER_ERROR_THRESHOLD_SECONDS', '60'))

# Initialize logger using the reusable configuration
logger = setup_app_logger(
    app_name=f"camera_stream_{CAMERA_ID or 'default'}",
    service_name="motion_detection",
    version=os.getenv('APP_VERSION', '1.0.0'),
    environment=os.getenv('ENVIRONMENT', 'development')
)

# Create MinIO client instance
minio_service = create_minio_client()
bucket_name = os.getenv("MINIO_BUCKET_NAME", None)

if not bucket_name:
    logger.error("❌ MINIO_BUCKET_NAME is not set in environment variables. Please check your .env file.")
    sys.exit(1)

# Initialize Kafka producer for motion detection events  
motion_producer = producer()

def compress_image(image, quality=COMPRESSION_QUALITY):
    """
    Compress image using JPEG with custom quality
    """
    try:
        # Convert from BGR (OpenCV) to RGB (PIL)
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(image_rgb)
        
        # Create buffer to hold compressed image
        with io.BytesIO() as buffer:
            # Save image with JPEG compression
            pil_image.save(buffer, format='JPEG', quality=quality, optimize=True)
            
            # Get compressed data
            compressed_data = buffer.getvalue()
            
        return compressed_data
    except Exception as e:
        logger.error(f"❌ Error compressing image: {e}")
        # Fallback to OpenCV compression
        _, buffer = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, quality])
        return buffer.tobytes()

def create_robust_capture(url, retries=3):
    """
    Create VideoCapture with robust configuration to handle H.264 errors
    """
    for attempt in range(retries):
        try:
            logger.info(f"🔄 Attempting to connect to camera, try {attempt + 1}...")
            backends = [cv2.CAP_FFMPEG, cv2.CAP_GSTREAMER, cv2.CAP_ANY]
            for backend in backends:
                cap = cv2.VideoCapture(url, backend)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                cap.set(cv2.CAP_PROP_FPS, 10)
                cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)
                cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)
                
                if cap.isOpened():
                    test_frames = 0
                    for _ in range(5):
                        ret, frame = cap.read()
                        if ret and frame is not None:
                            test_frames += 1
                    if test_frames >= 3:
                        logger.info(f"✅ Successfully connected with backend: {backend}")
                        return cap
                    else:
                        cap.release()
            time.sleep(2)
        except Exception as e:
            logger.error(f"❌ Connection error attempt {attempt + 1}: {e}")
            time.sleep(2)
    return None

class FrameReader:
    """
    Thread to read frames to avoid blocking the main thread.
    """
    def __init__(self, cap):
        self.cap = cap
        self.frame_queue = queue.Queue(maxsize=2)
        self.running = True
        self.thread = threading.Thread(target=self._read_frames)
        self.thread.daemon = True
        self.thread.start()
    
    def _read_frames(self):
        consecutive_failures = 0
        max_failures = 10
        while self.running:
            try:
                ret, frame = self.cap.read()
                if ret and frame is not None:
                    consecutive_failures = 0
                    # Add frame to queue, replacing oldest if full
                    if not self.frame_queue.full():
                        self.frame_queue.put((True, frame))
                    else:
                        try:
                            self.frame_queue.get_nowait()  # Remove oldest frame
                            self.frame_queue.put((True, frame))  # Add new frame
                        except queue.Empty:
                            pass
                else:
                    consecutive_failures += 1
                    if consecutive_failures >= max_failures:
                        logger.warning(f"⚠️ Too many consecutive frame read errors: {consecutive_failures}")
                        self.frame_queue.put((False, None))
                        break
                time.sleep(0.03)  # Small delay to prevent excessive CPU usage
            except Exception as e:
                consecutive_failures += 1
                logger.error(f"🔴 Frame read error: {e}")
                if consecutive_failures >= max_failures:
                    self.frame_queue.put((False, None))
                    break
    
    def get_frame(self):
        """Get a frame from the queue with timeout"""
        try:
            return self.frame_queue.get(timeout=1.0)
        except queue.Empty:
            return False, None
    
    def stop(self):
        """Stop the frame reading thread"""
        self.running = False
        if self.thread.is_alive():
            self.thread.join(timeout=2)

def detect_motion_between_frames(prev_gray, curr_gray):
    """
    Detect motion between 2 frames.
    """
    try:
        # Calculate absolute difference between frames
        frame_diff = cv2.absdiff(prev_gray, curr_gray)
        
        # Apply threshold to get binary image
        _, thresh = cv2.threshold(frame_diff, 25, 255, cv2.THRESH_BINARY)
        
        # Apply morphological operations to reduce noise
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        thresh = cv2.dilate(thresh, kernel, iterations=2)
        
        # Find contours in the thresholded image
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Calculate total motion area and filter small contours
        total_motion_area = 0
        valid_contours = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > MIN_CONTOUR_AREA:
                total_motion_area += area
                valid_contours.append(contour)
        
        # Determine if motion is significant based on threshold
        has_motion = total_motion_area > MOTION_THRESHOLD
        
        if DEBUG_MODE:
            logger.debug(f"Debug: Total contours: {len(contours)}, Valid: {len(valid_contours)}, Area: {total_motion_area:.0f}")
        
        return {
            'has_motion': has_motion,
            'total_area': total_motion_area,
            'valid_contours': valid_contours,
            'thresh_image': thresh
        }
    except Exception as e:
        logger.error(f"Error in detect_motion_between_frames: {e}")
        return {'has_motion': False, 'total_area': 0, 'valid_contours': [], 'thresh_image': None}

def delivery_report(err, msg):
    """Callback called when a message is sent (or fails)"""
    if err is not None:
        logger.error("Kafka message delivery failed", extra={
            'error': str(err),
            'topic': msg.topic() if msg else None
        })
    else:
        logger.debug("Kafka message delivered successfully", extra={
            'topic': msg.topic(),
            'partition': msg.partition(),
            'offset': msg.offset(),
            'message_size_bytes': len(msg.value()) if msg.value() else 0
        })

def send_message(image, contour_area):
    """Send motion detection message to Kafka"""
    camera_id = CAMERA_ID or 'default_camera'
    
    date_str = time.strftime("%Y-%m-%d")
    compressed_image = compress_image(image=image, quality=COMPRESSION_QUALITY)

    try:
        image_path = f"{date_str}/{camera_id}/{int(time.time() * 1000)}.jpg"
        minio_service.upload_image_bytes(
            bucket_name=bucket_name,
            object_name=image_path,
            image_bytes=compressed_image,
            content_type='image/jpeg'
        )
            
        motion_data = {
            'camera_id': camera_id,
            'timestamp': int(time.time() * 1000), 
            'motion_area': contour_area,
            'frame_dimensions': {
                'width': image.shape[1],
                'height': image.shape[0]  
            },
            'image_path': image_path,
            'compression_quality': COMPRESSION_QUALITY,
            'original_size': len(image.tobytes()),
            'compressed_size': len(compressed_image)
        }
        motion_producer.send_frame(motion_data, key=camera_id.encode('utf-8'))
        
        # Structured logging with additional context
        logger.info("Motion detected - image sent to Kafka", extra={
            'motion_area_pixels': motion_data['motion_area'],
            'frame_width': motion_data['frame_dimensions']['width'],
            'frame_height': motion_data['frame_dimensions']['height'],
            'original_size_bytes': len(image.tobytes()),
            'compressed_size_bytes': len(compressed_image),
            'compression_ratio': round(len(compressed_image) / len(image.tobytes()), 3),
            'compression_quality': COMPRESSION_QUALITY,
            'timestamp_ms': motion_data['timestamp']
        })

    except KafkaBufferException as e:
        logger.error("🔴 CRITICAL: Kafka buffer errors persisted beyond threshold - forcing container restart", extra={
            'error': str(e),
            'motion_area_pixels': contour_area,
            'frame_width': image.shape[1] if image is not None else None,
            'frame_height': image.shape[0] if image is not None else None
        }, exc_info=True)
        # Force container restart by exiting with error code
        sys.exit(1)
    except Exception as e:
        logger.error("Failed to send motion detection message", extra={
            'error': str(e),
            'motion_area_pixels': contour_area,
            'frame_width': image.shape[1] if image is not None else None,
            'frame_height': image.shape[0] if image is not None else None
        }, exc_info=True)
        return False

def motion_detect():
    """
    Run the entire process of connecting to camera, detecting motion, and sending to Kafka.
    """
    cap = create_robust_capture(CAMERA_URL)
    
    if cap is None:
        logger.error("❌ Unable to connect to camera after multiple attempts. Exiting.")
        return 

    logger.info(f"✅ Connected to camera. Checking for motion every {CHECK_INTERVAL} seconds...")
    logger.info("Press Ctrl+C to stop the program.")
    
    frame_reader = FrameReader(cap)
    frame_history = deque(maxlen=2)
    
    last_processed_check_time = time.time()
    frame_skip_count = 0

    try:
        while True:
            ret, frame = frame_reader.get_frame()
            
            if not ret or frame is None:
                frame_skip_count += 1
                logger.warning(f"⚠️ Skipping error frame #{frame_skip_count}")
                
                # If too many consecutive frame errors, try reconnecting to camera
                if frame_skip_count > 50:
                    logger.error("❌ Too many frame errors. Attempting to reconnect...")
                    frame_reader.stop()
                    cap.release()
                    
                    cap = create_robust_capture(CAMERA_URL)
                    if cap is None:
                        logger.error("❌ Unable to reconnect to camera. Exiting.")
                        break
                    
                    frame_reader = FrameReader(cap)
                    frame_skip_count = 0
                    frame_history.clear()
                
                time.sleep(0.1)
                continue
            
            frame_skip_count = 0
            current_time = time.time()
            
            # Only process and check for motion when CHECK_INTERVAL time has elapsed
            if current_time - last_processed_check_time >= CHECK_INTERVAL:
                try:
                    # Validate frame dimensions
                    if frame.shape[0] < 100 or frame.shape[1] < 100:
                        logger.warning("⚠️ Frame too small, skipping")
                        continue
                    
                    # Convert to grayscale and apply Gaussian blur
                    gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    gray_frame = cv2.GaussianBlur(gray_frame, (BLUR_SIZE, BLUR_SIZE), 0)
                    
                    # Store frame in history for motion detection
                    frame_history.append({
                        'gray': gray_frame,
                        'color': frame.copy(),
                        'timestamp': current_time
                    })
                    
                    # Perform motion detection when we have two frames
                    if len(frame_history) == 2:
                        motion_data = detect_motion_between_frames(
                            frame_history[0]['gray'],
                            frame_history[1]['gray']
                        )
                        
                        if motion_data['has_motion']:
                            # Send Kafka message when motion is detected
                            send_message(
                                frame_history[1]['color'],  # Send original color frame when motion detected
                                motion_data['total_area'],
                            )
                        else:
                            if DEBUG_MODE:
                                logger.debug(f"⚪ No significant motion (Area: {motion_data['total_area']:.0f}, Required: {MOTION_THRESHOLD})")
                    
                    # Update last processed time
                    last_processed_check_time = current_time
                    
                except Exception as e:
                    logger.error(f"🔴 Frame processing error: {e}")
                    continue
            
            time.sleep(0.05)  # Small delay to prevent excessive CPU usage
            
    except KeyboardInterrupt:
        logger.info("\n🛑 Stopping program...")
    except KafkaBufferException as e:
        logger.error("🔴 CRITICAL: Kafka buffer errors exceeded threshold - forcing container restart", extra={
            'error': str(e)
        }, exc_info=True)
        # Force container restart by exiting with error code
        sys.exit(1)
    except Exception as e:
        logger.error(f"🔴 Unexpected error: {e}")
        # For unexpected errors, also exit to allow Docker restart
        sys.exit(1)
    finally:
        # Ensure resources are released and producer is flushed when program ends
        if frame_reader:
            frame_reader.stop()
        if cap:
            cap.release()
        motion_producer.flush()
        logger.info("✅ Resources released and producer stopped.")

if __name__ == "__main__":
    motion_detect()