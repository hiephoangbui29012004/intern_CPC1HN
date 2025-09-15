import cv2
import numpy as np
from kafka.camera_stream_consumer import CameraStreamConsumer
from utils.logger_config import setup_app_logger
from minio_utils.minio_service import MinioService
from database_utils.mssql_service import DatabaseService
import os
import time
import asyncio
import uuid
from datetime import datetime
from ultralytics import YOLO

MODEL_PATH = os.getenv('MODEL_PATH')

minio_service = MinioService() 
yolo_model = YOLO(MODEL_PATH)
logger = setup_app_logger(
    app_name=f"c-mask-detection",
    service_name="mask-detection",
    version=os.getenv('APP_VERSION', '1.0.0'),
    environment=os.getenv('ENVIRONMENT', 'development')
)

def mask_detection_handler(image_bytes: bytes) -> dict:
    global yolo_model

    try:
        np_arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if(img is None):
            raise ValueError("Could not decode image bytes to OpenCV format")
        
        bounding_boxes = []
        mask_violations_found = False
        results = yolo_model(img)

        for r in results:
            img = r.plot()
            for box in r.boxes:
                cls_id = int(box.cls)
                class_name = yolo_model.names.get(cls_id, f"Unknown Class {cls_id}")
                
                xywh_norm = box.xywhn[0].tolist() 
                x_center_norm, y_center_norm, box_width_norm, box_height_norm = xywh_norm

                img_height, img_width, _ = img.shape
                
                box_info = {
                    "X": float(x_center_norm * img_width),
                    "Y": float(y_center_norm * img_height),
                    "Width": float(box_width_norm * img_width),
                    "Height": float(box_height_norm * img_height),
                    "Accuracy": float(box.conf[0]) * 100, 
                    "Label": class_name
                }
                bounding_boxes.append(box_info)

                if class_name.lower() in ['no_mask', 'without_mask']:
                    mask_violations_found = True 
        is_success, im_buf_arr = cv2.imencode(".jpg", img)
        image_bytes = im_buf_arr.tobytes()

        return {
            "mask_violations_found": mask_violations_found,
            "bounding_boxes": bounding_boxes,
            "image_bytes": image_bytes
        }

    except Exception as e:
        logger.error(f"Error in mask_detection_handler: {e}")
        raise e

async def save_detection_results(id, image_bytes, camera_id, capture_time, processing_start_time, processing_duration_ms, bounding_boxes):
    db_service = DatabaseService()
    tasks = [
        # Coroutine factory to upload image bytes to MinIO
        asyncio.to_thread(
            minio_service.upload_image_bytes,
            minio_service.bucket_name,
            f"{id}.jpg",
            image_bytes,
        ),
        # Coroutine factory to save detection results to database
        db_service.save_detection_results(
            result_id=id,
            camera_id=camera_id,
            capture_time=capture_time,
            processing_start_time=processing_start_time,
            processing_duration_ms=processing_duration_ms,
            bounding_boxes=bounding_boxes
        )
    ]

    await asyncio.gather(*tasks)

def message_handler(message: dict):
    start = datetime.now()
    data = message["data"]
    metadata = message["metadata"]
    timestamp_ms_kafka = metadata.get('timestamp', (None, None))[1]
    capture_time = datetime.fromtimestamp(timestamp_ms_kafka / 1000) if timestamp_ms_kafka else datetime.now()

    if 'compressed_image' not in data or not data['compressed_image']:
        logger.error("No compressed image found in message data")
        return True

    results = mask_detection_handler(data['compressed_image'])
    mask_violations_found = results.get("mask_violations_found", False)
    bounding_boxes = results.get("bounding_boxes", [])
    image_bytes = results.get("image_bytes", data['compressed_image']) 

    if not mask_violations_found:
        logger.info("No mask violations found")
        return True

    end = datetime.now()
    processing_duration_ms = int((end - start).total_seconds() * 1000)

    result_id = str(uuid.uuid4()) 
    camera_id = data.get('camera_id', 'UnknownCamera')

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            task = loop.create_task(save_detection_results(
                id=result_id,
                image_bytes=image_bytes,
                camera_id=camera_id,
                capture_time=capture_time,
                processing_start_time=start,
                processing_duration_ms=processing_duration_ms,
                bounding_boxes=bounding_boxes
            ))
            asyncio.run_coroutine_threadsafe(task, loop).result()
        else:
            asyncio.run(save_detection_results(
                id=result_id,
                image_bytes=image_bytes,
                camera_id=camera_id,
                capture_time=capture_time,
                processing_start_time=start,
                processing_duration_ms=processing_duration_ms,
                bounding_boxes=bounding_boxes
            ))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(save_detection_results(
                id=result_id,
                image_bytes=image_bytes,
                camera_id=camera_id,
                capture_time=capture_time,
                processing_start_time=start,
                processing_duration_ms=processing_duration_ms,
                bounding_boxes=bounding_boxes
            ))
        finally:
            pending = asyncio.all_tasks(loop)
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()

    return True

if __name__ == "__main__":
    camera_consumer = CameraStreamConsumer()

    try:
        camera_consumer.consume_messages(
            message_handler=message_handler,
            max_retries=3,
            retry_delay=5.0
        )
    except Exception as e:
        logger.error(f"Error occurred: {e}")
    finally:
        camera_consumer.close()
