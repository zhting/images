import os
import hashlib
from PIL import Image, ImageOps
import io

class ThumbnailService:
    def __init__(self, cache_dir="./assets/.cache/thumbnails"):
        self.cache_dir = cache_dir
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir, exist_ok=True)

    def get_thumbnail_path(self, file_path: str) -> str:
        # MD5 of the file path to serve as cache filename
        hash_name = hashlib.md5(file_path.encode('utf-8')).hexdigest()
        return os.path.join(self.cache_dir, f"{hash_name}.jpg")

    def get_thumbnail(self, file_path: str, max_size=(300, 300)) -> str:
        """
        Returns the path to the cached thumbnail. Generates it if missing or outdated.
        """
        if not os.path.exists(file_path):
            return None

        thumb_path = self.get_thumbnail_path(file_path)
        
        # Check if cache is valid
        if os.path.exists(thumb_path):
            src_mtime = os.path.getmtime(file_path)
            thumb_mtime = os.path.getmtime(thumb_path)
            if thumb_mtime >= src_mtime:
                return thumb_path
        
        # Generate
        try:
            # Check if video
            lower_path = file_path.lower()
            if lower_path.endswith(('.mp4', '.mov', '.avi', '.mkv')):
                import cv2
                import numpy as np
                cap = cv2.VideoCapture(file_path)
                if cap.isOpened():
                    # Read first frame (or seek to 1s?)
                    # Let's try to get near start but not black frame
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 30) # 30th frame ~ 1s if 30fps
                    ret, frame = cap.read()
                    if not ret:
                        # Fallback to 0
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        ret, frame = cap.read()
                    
                    cap.release()
                    
                    if ret:
                        # BGR -> RGB
                        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        img = Image.fromarray(frame)
                        img.thumbnail(max_size, Image.Resampling.BICUBIC)
                        img.save(thumb_path, "JPEG", quality=80)
                        return thumb_path
                return None # Failed to extract
            else:
                # Image
                with Image.open(file_path) as img:
                    # Auto-orient (handle EXIF rotation)
                    img = ImageOps.exif_transpose(img)
                    
                    # Convert to RGB if needed (e.g. PNG with alpha)
                    if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                        img = img.convert('RGB')
                    
                    img.thumbnail(max_size, Image.Resampling.BICUBIC)
                    img.save(thumb_path, "JPEG", quality=80)
                return thumb_path
        except Exception as e:
            print(f"Error generating thumbnail for {file_path}: {e}")
            return None

# Singleton instance
thumbnail_service = ThumbnailService()
