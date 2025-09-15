import asyncio
from prisma import Prisma
import uuid
import datetime
import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
logger.setLevel(logging.INFO)
class DatabaseService:
    def __init__(self):
        self.prisma = Prisma()
    #Kết nối, ngắt kết nối DB
    async def connect(self):
        """Kết nối tới cơ sở dữ liệu."""
        try:
            await self.prisma.connect()
        except Exception as e:
            raise
    async def disconnect(self):
        """Ngắt kết nối tới cơ sở dữ liệu."""
        try:
            await self.prisma.disconnect()
        except Exception as e:
            raise
    async def save_detection_results(
        self,
        result_id: str,
        camera_id: str,
        capture_time: datetime.datetime,
        processing_start_time: datetime.datetime,
        processing_duration_ms: int,
        bounding_boxes: list[dict]
    ) -> str:
        """
        Lưu kết quả nhận diện và các bounding box vào cơ sở dữ liệu.
        Args:
            camera_id (str): ID của camera.
            capture_time (datetime.datetime): Thời gian ảnh được chụp.
            processing_start_time (datetime.datetime): Thời gian bắt đầu xử lý ảnh.
            processing_duration_ms (int): Thời gian xử lý ảnh (miligiây).
            bounding_boxes (list[dict]): Danh sách các dictionary chứa thông tin bounding box.
                                         Mỗi dict phải có các key: 'Accuracy', 'Height', 'Width', 'X', 'Y', 'Label'.
        Returns:
            str: ID của bản ghi MD_Results đã được tạo.
        """
        try:
            await self.connect()
            async with self.prisma.tx() as t:
                # Tạo bản ghi MD_Results
                await t.md_results.create(
                    data={
                        "Id": result_id,
                        "CameraId": camera_id,
                        "CaptureTime": capture_time,
                        "ProcessingStartTime": processing_start_time,
                        "ProcessingDuration": processing_duration_ms,
                    }
                )
                if bounding_boxes:
                    result_box_data = [
                        {
                            "ResultId": result_id,
                            "Accuracy": box["Accuracy"],
                            "Height": box["Height"],
                            "Width": box["Width"],
                            "X": box["X"],
                            "Y": box["Y"],
                            "Label": box["Label"]
                        }
                        for box in bounding_boxes
                    ]
                    await t.md_resultbox.create_many(data=result_box_data)
            await self.disconnect()
            return result_id
        except Exception as e:
            print(f"Error saving detection results: {e}")
            logger.error(f"Error saving detection results: {e}")
            raise e
def create_database_service() -> DatabaseService:
    return DatabaseService()