from transformers import AutoModel, AutoProcessor
from PIL import Image
import torch
import numpy as np

class VisionModel:
    def __init__(self, model_name='google/siglip-so400m-patch14-384'):
        print(f"[VisionModel] Loading model: {model_name}...")
        
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[VisionModel] Using device: {self.device}")
        
        try:
            # SigLIP is supported by AutoModel (SiglipModel)
            self.model = AutoModel.from_pretrained(model_name).to(self.device)
            self.processor = AutoProcessor.from_pretrained(model_name)
            self.model.eval() # Inference mode
            print("[VisionModel] Model loaded via transformers.")
        except Exception as e:
            print(f"[VisionModel] Error loading model: {e}")
            raise e

    def encode(self, image: Image.Image) -> list[float]:
        """
        Encode an image into a vector.
        """
        if image.mode != "RGB":
            image = image.convert("RGB")
            
        with torch.no_grad():
            inputs = self.processor(images=image, return_tensors="pt").to(self.device)
            image_features = self.model.get_image_features(**inputs)
            # Normalize? SigLIP features are usually trained with log-sigmoid loss, 
            # but usually we want normalized vectors for cosine similarity.
            # get_image_features usually returns unnormalized? 
            # CLIP/SigLIP standard is to normalize for retrieval.
            image_features = image_features / image_features.norm(p=2, dim=-1, keepdim=True)
            return image_features[0].cpu().tolist()

    def encode_batch(self, images: list[Image.Image]) -> list[list[float]]:
        """
        Encode a batch of images.
        """
        if not images:
            return []
            
        # Ensure RGB
        rgb_images = [img.convert("RGB") if img.mode != "RGB" else img for img in images]
        
        with torch.no_grad():
            inputs = self.processor(images=rgb_images, return_tensors="pt").to(self.device)
            image_features = self.model.get_image_features(**inputs)
            image_features = image_features / image_features.norm(p=2, dim=-1, keepdim=True)
            return image_features.cpu().tolist()

    def encode_text(self, text: str) -> list[float]:
        """
        Encode text into a vector.
        """
        with torch.no_grad():
            inputs = self.processor(text=[text], return_tensors="pt", padding="max_length", truncation=True).to(self.device)
            text_features = self.model.get_text_features(**inputs)
            text_features = text_features / text_features.norm(p=2, dim=-1, keepdim=True)
            return text_features[0].cpu().tolist()

    def predict_aesthetic_score(self, image: Image.Image) -> float:
        """
        Predict aesthetic score (0-1) using Zero-Shot classification.
        Prompts: [Positive, Negative]
        """
        prompts = ["aesthetic, high quality, detail, sharp", "blurry, low quality, noisy, ugly"]
        
        with torch.no_grad():
            if image.mode != "RGB": image = image.convert("RGB")
            
            # Prepare inputs
            inputs = self.processor(
                text=prompts, 
                images=image, 
                return_tensors="pt", 
                padding=True
            ).to(self.device)
            
            # Forward
            outputs = self.model(**inputs)
            
            # Logic: SigLIP/CLIP logits_per_image is (batch, num_classes)
            # We want probability of "aesthetic" class
            logits_per_image = outputs.logits_per_image # this is image @ text.T * logit_scale
            probs = logits_per_image.softmax(dim=1) # (1, 2)
            
            # Score is prob of class 0
            score = probs[0][0].item()
            return score

    def classify_type(self, image: Image.Image) -> str:
        """
        Classify image type: 'photo', 'screenshot', 'document'
        """
        labels = ["photo", "screenshot", "document"]
        prompts = [
            "a photo of a person, animal, food, object, or scene", 
            "a digital screen capture of an app or interface", 
            "a detailed scanned document or page consisting primarily of dense text"
        ]
        
        with torch.no_grad():
            if image.mode != "RGB": image = image.convert("RGB")
            
            inputs = self.processor(
                text=prompts, 
                images=image, 
                return_tensors="pt", 
                padding=True
            ).to(self.device)
            
            outputs = self.model(**inputs)
            logits_per_image = outputs.logits_per_image
            probs = logits_per_image.softmax(dim=1)
            
            # Get max index
            max_idx = probs.argmax().item()
            return labels[max_idx]
