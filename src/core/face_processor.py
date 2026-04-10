import logging
import numpy as np
import os
import cv2
from PIL import Image
from sklearn.cluster import DBSCAN

# InsightFace
try:
    import insightface
    from insightface.app import FaceAnalysis
except ImportError:
    insightface = None

logger = logging.getLogger(__name__)

class FaceProcessor:
    def __init__(self, provider="cpu"):
        if insightface is None:
            logger.error("InsightFace not installed. Face features disabled.")
            self.app = None
            return

        # Initialize FaceAnalysis
        # providers: ['CUDAExecutionProvider', 'CPUExecutionProvider']
        # 'buffalo_l' is the default model pack (detection + recognition)
        # allowed_modules=['detection', 'recognition']
        
        providers = ['CPUExecutionProvider']
        if provider == "cuda":
            providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
            
        self.app = FaceAnalysis(name='buffalo_l', providers=providers)
        # det_thresh=0.5 is default. Increasing to 0.85 to filter statues/artifacts/background.
        self.app.prepare(ctx_id=0, det_size=(640, 640), det_thresh=0.5)
        
    def detect_faces(self, image: Image.Image):
        """
        Detect faces in PIL Image.
        Returns list of dicts: {'bbox': [x,y,w,h], 'embedding': np.array, 'det_score': float}
        """
        if not self.app:
            return []
            
        try:
            # InsightFace expects cv2 image (BGR numpy array)
            # Convert PIL RGB -> CV2 BGR
            img_np = np.array(image)
            img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
            
            faces = self.app.get(img_bgr)
            
            results = []
            for face in faces:
                # Filter low confidence (double check)
                if face.det_score < 0.5:
                    continue

                # Filter small faces (often noise or background artifacts)
                # bbox is [x1, y1, x2, y2]
                w = face.bbox[2] - face.bbox[0]
                h = face.bbox[3] - face.bbox[1]
                if w < 30 or h < 30: # Ignore faces smaller than 30x30
                    continue

                results.append({
                    "bbox": face.bbox.tolist(),
                    "embedding": face.embedding, # Keep as numpy for DB/Clustering
                    "det_score": float(face.det_score)
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Face detection error: {e}")
            return []

    def cluster_faces(self, embeddings, eps=0.45, min_samples=3):
        """
        Cluster face embeddings using DBSCAN.
        embeddings: list or array of (N, 512)
        Returns: labels (array of cluster IDs, -1 is noise)
        """
        if not embeddings or len(embeddings) == 0:
            return []
            
        try:
            # Normalize embeddings first? InsightFace embeddings are usually normalized.
            # But let's ensure unit length if needed. 
            # Usually they are.
            
            # DBSCAN metric='cosine' is best for embeddings, but sklearn dbscan with cosine distance
            # eps should be small (e.g. 0.3 - 0.5 distance).
            # If feature vectors are normalized, euclidean distance relates to cosine.
            # dist = 1 - cos_sim. 
            # If 0.5 similarity is threshold, dist is 0.5.
            
            # Sklearn DBSCAN with metric='cosine':
            db = DBSCAN(eps=eps, min_samples=min_samples, metric='cosine')
            db.fit(embeddings)
            return db.labels_
            
        except Exception as e:
            logger.error(f"Face clustering error: {e}")
            return []

    def get_face_thumbnail(self, image_path, bbox):
        """
        Crop face from image file path.
        Returns PIL Image.
        """
        try:
            img = Image.open(image_path)
            # bbox is [x1, y1, x2, y2]
            # Add padding?
            x1, y1, x2, y2 = bbox
            
            # padding 20%
            w = x2 - x1
            h = y2 - y1
            pad_x = w * 0.2
            pad_y = h * 0.2
            
            img_w, img_h = img.size
            
            crop_x1 = max(0, x1 - pad_x)
            crop_y1 = max(0, y1 - pad_y)
            crop_x2 = min(img_w, x2 + pad_x)
            crop_y2 = min(img_h, y2 + pad_y)
            
            face_img = img.crop((crop_x1, crop_y1, crop_x2, crop_y2))
            return face_img
        except Exception:
            return None
