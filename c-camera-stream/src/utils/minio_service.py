import os
from minio import Minio
from minio.error import S3Error
from typing import Optional
from io import BytesIO
from dotenv import load_dotenv 
import logging

load_dotenv()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class MinioService: 
    def __init__(
        self,
        endpoint: str = os.getenv("MINIO_ENDPOINT"),
        access_key: str = os.getenv("MINIO_ACCESS_KEY"),
        secret_key: str = os.getenv("MINIO_SECRET_KEY"),
        secure: bool = True
    ):
        """
        Initialize MinIO client
        
        Args:
            endpoint: MinIO server endpoint (default: lấy từ MINIO_ENDPOINT trong .env)
            access_key: Access key for MinIO (default: lấy từ MINIO_ACCESS_KEY trong .env)
            secret_key: Secret key for MinIO (default: lấy từ MINIO_SECRET_KEY trong .env)
            secure: Use HTTPS if True (default: lấy từ MINIO_SECURE trong .env)
        """
        self.client = Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure
        )
        self.endpoint = endpoint
        self.bucket_name = os.getenv("MINIO_BUCKET_NAME")

    def upload_image_bytes(
        self,
        bucket_name: str,
        object_name: str,
        image_bytes: bytes,
        content_type: str = "image/jpeg"
    ) -> bool:
        """
        Upload image bytes to MinIO bucket
        
        Args:
            bucket_name: Name of the bucket
            object_name: Name of the object in MinIO
            image_bytes: Image data as bytes
            content_type: Content type of the image (default: image/jpeg)
        
        Returns:
            bool: True if upload successful, False otherwise
        """
        try:
            if not self.client.bucket_exists(bucket_name):
                self.client.make_bucket(bucket_name)
            
            image_stream = BytesIO(image_bytes)
        
            self.client.put_object(
                bucket_name=bucket_name,
                object_name=object_name,
                data=image_stream,
                length=len(image_bytes),
                content_type=content_type
            )

            logger.info(f"Successfully uploaded image bytes as {object_name} to bucket {bucket_name}")
            return True
            
        except S3Error as e:
            logger.error(f"S3 Error occurred: {e}")
            return False
        except Exception as e:
            logger.error(f"Error occurred during upload: {e}")
            return False


def create_minio_client( 
    endpoint: str = os.getenv("MINIO_ENDPOINT"),
    access_key: str = os.getenv("MINIO_ACCESS_KEY"), 
    secret_key: str = os.getenv("MINIO_SECRET_KEY"),
    secure: bool = (os.getenv("MINIO_SECURE", "true").lower() == "true")
) -> MinioService: 
    """
    Factory function to create MinIO client
    
    Returns:
        MinioService: Configured MinIO client instance
    """
    return MinioService(endpoint, access_key, secret_key, secure)

if __name__ == "__main__":
    minio_service = create_minio_client()
    logger.info(f"MinIO client created with endpoint: {minio_service.endpoint}")
    logger.info(f"Using bucket: {minio_service.bucket_name}")

    minio_service.upload_image_bytes(
        'test',
        'test_image.jpg',
        b'This is a test image byte content',
        content_type='image/jpeg'
    )