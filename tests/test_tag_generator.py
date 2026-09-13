"""TagGenerator: prompt-bank caching and image-embedding reuse.

The indexing pipeline hands its already-computed embedding to
generate_tags(); these tests pin that contract so a future change cannot
silently reintroduce the second vision-tower pass per photo.
"""
import numpy as np
import pytest
from PIL import Image

from core.tag_generator import TagGenerator


class RecordingModel:
    """Counts tower invocations so the tests can assert on them."""
    dim = 8

    def __init__(self):
        self.encode_calls = 0
        self.encode_text_calls = 0
        self.encode_text_batch_calls = 0

    def _vec(self, seed):
        rng = np.random.default_rng(abs(hash(seed)) % (2**32))
        v = rng.random(self.dim).astype("float32")
        return (v / np.linalg.norm(v)).tolist()

    def encode(self, image):
        self.encode_calls += 1
        return self._vec("image")

    def encode_text(self, text):
        self.encode_text_calls += 1
        return self._vec(text)

    def encode_text_batch(self, texts):
        self.encode_text_batch_calls += 1
        return [self._vec(t) for t in texts]


class LegacyModel(RecordingModel):
    """An older model object that only exposes single-string encode_text."""
    encode_text_batch = None


@pytest.fixture
def image():
    return Image.new("RGB", (16, 16), "blue")


def test_reuses_supplied_embedding_instead_of_re_encoding(image):
    model = RecordingModel()
    gen = TagGenerator(model)

    gen.generate_tags(image, image_features=model._vec("image"))

    assert model.encode_calls == 0, "generate_tags must not run a second vision pass"


def test_encodes_the_image_when_no_embedding_is_supplied(image):
    model = RecordingModel()
    gen = TagGenerator(model)

    gen.generate_tags(image)

    assert model.encode_calls == 1


def test_prompt_bank_is_encoded_once_in_a_single_batch(image):
    model = RecordingModel()
    gen = TagGenerator(model)

    gen.generate_tags(image, image_features=model._vec("image"))
    gen.generate_tags(image, image_features=model._vec("image"))

    assert model.encode_text_batch_calls == 1, "prompt bank must be cached across calls"
    assert model.encode_text_calls == 0, "batch path must not fall back to per-prompt encoding"
    assert gen.text_features.shape == (len(gen.categories), model.dim)


def test_falls_back_to_per_prompt_encoding_when_batch_is_unavailable(image):
    model = LegacyModel()
    gen = TagGenerator(model)

    gen.generate_tags(image, image_features=model._vec("image"))

    assert model.encode_text_calls == len(gen.prompts)
    assert gen.text_features.shape == (len(gen.categories), model.dim)


def test_returns_tags_from_the_vocabulary(image):
    model = RecordingModel()
    gen = TagGenerator(model)

    # An embedding equal to one prompt's vector must rank that tag first.
    target = gen.categories[3]
    tags = gen.generate_tags(image, image_features=model._vec(f"a photo of a {target}"))

    assert tags and tags[0] == target


def test_a_broken_model_degrades_to_no_tags(image):
    class Boom(RecordingModel):
        def encode_text_batch(self, texts):
            raise RuntimeError("text tower unavailable")

    assert TagGenerator(Boom()).generate_tags(image) == []
