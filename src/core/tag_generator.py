import logging
from typing import List
from PIL import Image

# Predefined categories for zero-shot tagging
# We can expand this list or make it configurable
# Predefined categories for zero-shot tagging
# Extended list for better coverage
tag_categories = [
    # Document/Screen
    "screenshot", "document", "meme", "text", "poster", "map", 
    # Animals
    "cat", "dog", "bird", "fish", "insect", "animal",
    # Food
    "food", "fruit", "vegetable", "drink", "coffee", "cake", "restaurant", "cooking",
    # Nature
    "landscape", "mountain", "beach", "ocean", "river", "lake", "forest", "tree", "flower", "grass", "sky", "cloud", "sunset", "snow", "rain",
    # People
    "portrait", "selfie", "daily life", "group photo", "child", "baby", "man", "woman", "crowd",
    # Places/Architecture
    "city", "street", "building", "house", "room", "bedroom", "living room", "kitchen", "bathroom", "office", "shop", "bridge", "road",
    # Objects
    "car", "bicycle", "train", "airplane", "boat", "chair", "table", "computer", "phone", "camera", "bag", "toy", "book", "art",
    # Activities/Events
    "party", "concert", "meeting", "wedding", "travel", "sports", "running", "swimming", "performance",
    # Time/Atmosphere
    "night", "daytime", "sunrise", "shadow", "reflection", "colorful", "dark", "bright"
]

# Prompt templates could improve accuracy "a photo of a {}"
prompts = [f"a photo of a {tag}" for tag in tag_categories]

class TagGenerator:
    def __init__(self, model):
        """
        Initialize with a VisionModel instance (SigLIP/CLIP).
        We reuse the global model to save memory.
        """
        self.model = model
        
        # Load categories from file
        self.categories = self._load_tags()
        self.prompts = [f"a photo of a {tag}" for tag in self.categories]
        
        # Pre-compute text embeddings for tags? 
        # VisionModel usually doesn't expose raw text encoder easily unless we dig in.
        # But `model.encode_text` is available.
        self.text_features = None

    def _load_tags(self):
        import os
        vocab_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets", "tags_vocab.txt")
        tags = []
        if os.path.exists(vocab_path):
            with open(vocab_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                         tags.append(line)
        
        if not tags:
            # Fallback
            tags = ["photo", "screenshot", "cat", "dog", "food", "person"]
            
        # Remove duplicates while preserving order
        unique_tags = []
        seen = set()
        for t in tags:
            if t not in seen:
                unique_tags.append(t)
                seen.add(t)
        return unique_tags

    def _ensure_text_features(self):
        if self.text_features is None:
            # Batch encode all prompts
            # Assuming model.encode_text can handle a list, or we loop
            # Check VisionModel signature... simple loop for now
            feats = []
            for p in self.prompts:
                feats.append(self.model.encode_text(p))
            
            # Stack into tensor if possible, or keep as list of arrays
            # VisionModel returns numpy arrays usually
            import numpy as np
            self.text_features = np.stack(feats)
            
            # Normalize? VisionModel.encode_text usually returns normalized if it's cosine ready.
            # Assuming they are normalized.

    def generate_tags(self, image: Image.Image, threshold: float = 0.2, top_k: int = 3) -> List[str]:
        """
        Generate tags for valid image.
        Returns list of strings.
        """
        try:
            self._ensure_text_features()
            
            # Encode image
            image_features = self.model.encode(image) # Returns numpy array (dim,)
            
            import numpy as np
            
            # Compute cosine similarity
            # text_features: (N, dim), image_features: (dim,)
            # similarity = text_features @ image_features.T
            
            similarity = self.text_features @ image_features
            
            # Get top_k indices
            indices = np.argsort(similarity)[::-1][:top_k]
            
            tags = []
            for idx in indices:
                score = similarity[idx]
                # Lower threshold for better recall with SigLIP
                if score >= 0.12:
                    tags.append(self.categories[idx])
            
            # Fallback: If no tags, take top 1 if it has some relevance
            if not tags and len(indices) > 0:
                 best_idx = indices[0]
                 if similarity[best_idx] > 0.08:
                     tags.append(self.categories[best_idx])

            return tags
            
        except Exception as e:
            logging.error(f"Tag generation failed: {e}")
            return []
