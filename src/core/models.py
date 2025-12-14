from sentence_transformers import SentenceTransformer
from PIL import Image
import numpy as np

import torch

class VisionModel:
    def __init__(self, model_name='clip-ViT-B-32'):
        # clip-ViT-B-32 outputs 512 dim vectors
        print(f"[VisionModel] Loading model: {model_name}...")
        
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[VisionModel] Using device: {self.device}")
        
        self.model = SentenceTransformer(model_name, device=self.device)
        print("[VisionModel] Model loaded.")

    def encode(self, image: Image.Image) -> list[float]:
        """
        Encode an image into a vector.
        Returns a list of floats (512 dim for ViT-B-32).
        """
        # sentence-transformers encode returns ndarray
        vector = self.model.encode(image)
        return vector.tolist()

    def encode_batch(self, images: list[Image.Image]) -> list[list[float]]:
        """
        Encode a batch of images.
        """
        if not images:
            return []
        vectors = self.model.encode(images, batch_size=len(images))
        return vectors.tolist()

    def encode_text(self, text: str) -> list[float]:
        """
        Encode text into a vector.
        """
        vector = self.model.encode(text)
        return vector.tolist()
