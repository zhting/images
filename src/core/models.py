import os
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

        # fp16 on CUDA roughly halves memory traffic and engages tensor
        # cores; embeddings move by ~1e-3 cosine, far below anything search
        # or tagging can notice, and stay in the same vector space as an
        # index built in fp32. CPU stays fp32 (fp16 matmul is slow there).
        # DEEPPHOTO_FP16=0 opts out.
        self.dtype = torch.float32
        if self.device == "cuda" and os.environ.get("DEEPPHOTO_FP16", "1") != "0":
            self.model.half()
            self.dtype = torch.float16
            logger.info("[VisionModel] Using fp16 on CUDA.")

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
                    feats = self._pooled(self.model.get_text_features(**inputs))
                    feats = feats / feats.norm(p=2, dim=-1, keepdim=True)
                bank = feats.cpu()
                self._text_bank_cache[key] = bank
        return bank

    @staticmethod
    def _pooled(feats):
        """get_*_features returns a tensor on most transformers versions and
        a BaseModelOutputWithPooling on some; normalise to fp32 tensor so
        everything downstream (norms, dot products, .tolist()) is
        identical whatever dtype the model runs in."""
        if hasattr(feats, "pooler_output"):
            feats = feats.pooler_output
        return feats.float()

    def preprocess(self, image: Image.Image):
        """Pixels -> model input tensor ``(3, H, W)`` on CPU.

        Pure CPU work with no model state, so the indexing pipeline runs it
        on worker threads: the expensive full-resolution resize happens in
        parallel with inference instead of in front of it, and workers can
        drop the decoded original as soon as this returns.
        """
        if image.mode != "RGB":
            image = image.convert("RGB")
        return self.processor(images=image, return_tensors="pt")["pixel_values"][0]

    def _image_features_from_pixels(self, pixel_values):
        """Batched vision-tower pass; returns normalized fp32 ``(N, D)`` on CPU."""
        with torch.no_grad():
            pixel_values = pixel_values.to(self.device, dtype=self.dtype)
            feats = self._pooled(self.model.get_image_features(pixel_values=pixel_values))
            feats = feats / feats.norm(p=2, dim=-1, keepdim=True)
        return feats.cpu()

    def _image_features(self, image: Image.Image):
        """One vision-tower forward pass; returns the normalized 1-D tensor."""
        return self._image_features_from_pixels(self.preprocess(image).unsqueeze(0))[0]

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
        return self._analyze_features(self._image_features(image).unsqueeze(0))[0]

    def analyze_batch(self, pixel_values: list) -> list[dict]:
        """``analyze()`` for many images in one forward pass.

        Takes the tensors produced by :meth:`preprocess`. Results are
        element-for-element what ``analyze()`` returns for each image.
        """
        if not len(pixel_values):
            return []
        return self._analyze_features(
            self._image_features_from_pixels(torch.stack(list(pixel_values))))

    def _analyze_features(self, feats) -> list[dict]:
        """Zero-shot score/tag for a batch of normalized embeddings ``(N, D)``."""
        scale = self._logit_scale()

        aesthetic = self._text_bank("aesthetic", self.AESTHETIC_PROMPTS)
        # logit_bias is identical for every class, so it cancels in the softmax.
        a_logits = (feats @ aesthetic.T) * scale
        scores = torch.softmax(a_logits, dim=-1)[:, 0]

        type_bank = self._text_bank("type", self.TYPE_PROMPTS)
        # argmax is invariant under the positive affine logit transform.
        tags = torch.argmax(feats @ type_bank.T, dim=-1)

        return [{
            "embedding": feats[i].tolist(),
            "aesthetic_score": float(scores[i].item()),
            "tag": self.TYPE_LABELS[int(tags[i].item())],
        } for i in range(feats.shape[0])]

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
            
        return self._image_features_from_pixels(
            torch.stack([self.preprocess(img) for img in images])).tolist()

    def encode_text(self, text: str) -> list[float]:
        """
        Encode text into a vector.
        """
        with torch.no_grad():
            inputs = self.processor(text=[text], return_tensors="pt", padding="max_length", truncation=True).to(self.device)
            text_features = self._pooled(self.model.get_text_features(**inputs))
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
            feats = self._pooled(self.model.get_text_features(**inputs))
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
