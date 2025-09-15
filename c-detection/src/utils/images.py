from PIL import Image
import cv2
import io

def compress_image(image, quality=80):
    """
    Compress image using JPEG with custom quality
    """
    try:
        # Convert from BGR (OpenCV) to RGB (PIL)
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(image_rgb)

        # Create buffer to hold compressed image
        buffer = io.BytesIO()

        # Save image with JPEG compression
        pil_image.save(buffer, format='JPEG', quality=quality, optimize=True)

        # Get compressed data
        compressed_data = buffer.getvalue()
        buffer.close()
        
        return compressed_data
    except Exception as e:
        print(f"❌ Compress image error: {e}")
        # Fallback to OpenCV compression
        _, buffer = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, quality])
        return buffer.tobytes()