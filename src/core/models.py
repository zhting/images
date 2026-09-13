import threading

from transformers import AutoModel, AutoProcessor
from PIL import Image
import torch

import logging
logger = logging.getLogger(__name__)

class VisionModel:
    # Constant zero-shot prompt banks (encoded once, see _text_bank).
    AESTHETIC_PROMPTS = ["aesthetic, high quality, detail, sharp",
                         "blurry, low quality, noisy, ugly"]
    TYPE_LABELS = ["photo", "screenshot", "document"]
    TYPE_PROMPTS = [
        "a photo of real world scenes, people, or objects",
        "a digital screenshot of computer or phone interface",
        "a document, paper, or page containing lines of text",
    ]

    def __init__(self, model_name='google/siglip-so400m-patch14-384'):
        logger.info(f"[VisionModel] Loading model: {model_name}...")
        
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"[VisionModel] Using device: {self.device}")
        
        try:
            # SigLIP is supported by AutoModel (SiglipModel)
            self.model = AutoModel.from_pretrained(model_name).to(self.device)
            self.processor = AutoProcessor.from_pretrained(model_name)
            self.model.eval() # Inference mode
            logger.info("[VisionModel] Model loaded via transformers.")
        except Exception as e:
            logger.error(f"[VisionModel] Error loading model: {e}")
            raise e

        # Zero-shot prompt banks are constant, so their text embeddings are
        # computed once and reused for every photo instead of being re-encoded
        # on each call (the old predict_aesthetic_score / classify_type ran
        # the text tower again for every single image).
        self._text_bank_cache: dict = {}
        self._bank_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Zero-shot helpers
    # ------------------------------------------------------------------
    def _logit_scale(self) -> float:
        """SigLIP's learned temperature; 1.0 if the model does not expose it."""
        try:
            return float(self.model.logit_scale.exp().item())
        except Exception:
            return 1.0

    def _text_bank(self, key: str, prompts: list[str]):
        """Normalized text embeddings for a fixed prompt list, encoded once."""
        bank = self._text_bank_cache.get(key)
        if bank is not None:
            return bank
        with self._bank_lock:
            bank = self._text_bank_cache.get(key)
            if bank is None:
                with torch.no_grad():
                    inputs = self.processor(
                        text=prompts, return_tensors="pt",
                        padding="max_length", truncation=True).to(self.device)
                    feats = self.model.get_text_features(**inputs)
                    if hasattr(feats, "pooler_output"):
                        feats = feats.pooler_output
                    feats = feats / feats.norm(p=2, dim=-1, keepdim=True)
                bank = feats.cpu()
                self._text_bank_cache[key] = bank
        return bank

    def _image_features(self, image: Image.Image):
        """One vision-tower forward pass; returns the normalized 1-D tensor."""
        if image.mode != "RGB":
            image = image.convert("RGB")
        with torch.no_grad():
            inputs = self.processor(images=image, return_tensors="pt").to(self.device)
            feats = self.model.get_image_features(**inputs)
            if hasattr(feats, "pooler_output"):
                feats = feats.pooler_output
            feats = feats / feats.norm(p=2, dim=-1, keepdim=True)
        return feats[0].cpu()

    def analyze(self, image: Image.Image) -> dict:
        """Embedding + aesthetic score + type tag from a *single* forward pass.

        The indexing pipeline previously called encode(), predict_aesthetic_score(),
        classify_type() and TagGenerator.generate_tags() separately — four full
        SigLIP-SO400M vision passes over the same pixels, plus a text pass over
        constant prompts each time.  Zero-shot classification only needs the
        normalized image embedding dotted against the (cached) text embeddings,
        so one pass answers all of it.

        Returns ``{"embedding", "aesthetic_score", "tag"}``.
        """
        feats = self._image_features(image)
        scale = self._logit_scale()

        aesthetic = self._text_bank("aesthetic", self.AESTHETIC_PROMPTS)
        # logit_bias is identical for every class, so it cancels in the softmax.
        a_logits = (aesthetic @ feats) * scale
        score = float(torch.softmax(a_logits, dim=0)[0].item())

        type_bank = self._text_bank("type", self.TYPE_PROMPTS)
        # argmax is invariant under the positive affine logit transform.
        tag = self.TYPE_LABELS[int(torch.argmax(type_bank @ feats).item())]

        return {
            "embedding": feats.tolist(),
            "aesthetic_score": score,
            "tag": tag,
        }

    def encode(self, image: Image.Image) -> list[float]:
        """
        Encode an image into a vector.
        """
        return self._image_features(image).tolist()

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
            if hasattr(image_features, "pooler_output"):
                image_features = image_features.pooler_output
            image_features = image_features / image_features.norm(p=2, dim=-1, keepdim=True)
            return image_features.cpu().tolist()

    def encode_text(self, text: str) -> list[float]:
        """
        Encode text into a vector.
        """
        with torch.no_grad():
            inputs = self.processor(text=[text], return_tensors="pt", padding="max_length", truncation=True).to(self.device)
            text_features = self.model.get_text_features(**inputs)
            if hasattr(text_features, "pooler_output"):
                text_features = text_features.pooler_output
            text_features = text_features / text_features.norm(p=2, dim=-1, keepdim=True)
            return text_features[0].cpu().tolist()

    def encode_text_batch(self, texts: list[str]) -> list[list[float]]:
        """Encode many strings in one text-tower pass.

        TagGenerator warms ~100 tag prompts at startup; looping encode_text
        paid ~100 separate forward passes for what is a single batch.
        """
        if not texts:
            return []
        with torch.no_grad():
            inputs = self.processor(text=texts, return_tensors="pt",
                                    padding="max_length", truncation=True).to(self.device)
            feats = self.model.get_text_features(**inputs)
            if hasattr(feats, "pooler_output"):
                feats = feats.pooler_output
            feats = feats / feats.norm(p=2, dim=-1, keepdim=True)
            return feats.cpu().tolist()

    def predict_aesthetic_score(self, image: Image.Image) -> float:
        """
        Predict aesthetic score (0-1) using Zero-Shot classification.
        Prefer analyze() when the tag/embedding are wanted too — it shares
        the one vision pass instead of running another.
        """
        return self.analyze(image)["aesthetic_score"]

    def classify_type(self, image: Image.Image) -> str:
        """
        Classify image type: 'photo', 'screenshot', 'document'.
        Prefer analyze() when the score/embedding are wanted too.
        """
        return self.analyze(image)["tag"]
