from typing import List

import numpy as np
import numpy.typing as npt
from openai import OpenAI
from sentence_transformers import SentenceTransformer

from .base import Embedder

__all__ = [
    'OpenAIEmbedder',
    'SentenceTransformerEmbedder',
]

_models = [
    'sentence-transformers/all-MiniLM-L6-v2',
    'hkunlp/instructor-xl',
]


class OpenAIEmbedder(Embedder):
    """
    Util class to call OpenAI embeddings.
    """

    def __init__(self, model_name: str = "text-embedding-3-large"):
        self.model_name = model_name
        self.client = OpenAI()

        # Deduce dimension by encoding a dummy text
        dummy_emb = self.encode([""])
        self._dim = dummy_emb.shape[1]

    def encode(self, texts: List[str], prefix: str, **kwargs):
        embeddings: List[List[float]] = []

        if prefix:
            texts = [f"{prefix}; {text}" for text in texts]

        for text in texts:
            response = self.client.embeddings.create(input=text, model=self.model_name, **kwargs)
            embeddings.append(response.data[0].embedding)

        return np.array(embeddings)

    @property
    def dimension(self) -> int:
        return self._dim


class SentenceTransformerEmbedder(Embedder):
    """
    Embedder that wraps SentenceTransformer from the sentence-transformers
    library.
    """

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    ):
        self.model_name = model_name
        self._model = SentenceTransformer(model_name)

        # Deduce dimension by encoding a dummy text
        dummy_emb = self._model.encode([""], convert_to_numpy=True)
        self._dim = dummy_emb.shape[1]

    def encode(self, texts: List[str], prefix: str | None = None) -> npt.NDArray:
        if prefix:
            texts = [f"{prefix}; {text}" for text in texts]

        embs = self._model.encode(texts, convert_to_numpy=True)
        return embs.astype(np.float32)

    @property
    def dimension(self) -> int:
        return self._dim
