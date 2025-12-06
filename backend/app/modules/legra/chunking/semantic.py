from itertools import pairwise
from typing import List

import nltk
import numpy as np
import numpy.typing as npt
from sentence_transformers import SentenceTransformer

from .base import Chunker

nltk.download('punkt_tab', quiet=True)

__all__ = [
    'SemanticChunker',
]


def _merge_to_min_length(strings: List[str], min_len: int, sep: str = " ") -> List[str]:
    """
    Merge sentences such that each sentence has a length at least min_len. A
    short sentence is merged with its successor.
    """
    merged = []
    i = 0
    n = len(strings)
    while i < n:
        current = strings[i]
        while len(current) < min_len and i + 1 < n:
            i += 1
            current = sep.join([current, strings[i]])
        merged.append(current)
        i += 1
    return merged


class SemanticChunker(Chunker):
    """
    Chunk text based on semantic breaks between adjacent sentences. Consecutive
    sentences with lowest cosine similarity define split seeds. Recursively
    apply until each chunk has between [min_sents, max_sents].
    """

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        min_sents: int = 1,
        max_sents: int = 50,
        min_sent_length: int = 16,
    ):
        if max_sents < 1:
            raise ValueError("max_sents must be >= 1")
        if min_sents > max_sents:
            raise ValueError("min_sents <= max_sents required.")

        self.model = SentenceTransformer(model_name)
        self.min_sents = min_sents
        self.max_sents = max_sents
        self.min_sent_length = min_sent_length

    @staticmethod
    def _sentence_split(text: str) -> List[str]:
        """
        Splits text into sentences.
        """
        return nltk.tokenize.sent_tokenize(text)

    def _balance_chunks(
        self,
        sims: npt.NDArray,
        start: int,
        end: int,
    ) -> List[int]:
        """
        Recursively find the indices where similarity between consecutive
        sentences is smallest so that each subgroup of sentences does not exceed
        the max chunk size.

        start (inclusive) and end (exclusive) specify the interval in sims to
        use. I.e., the sentences that will be considered are in
        sents[start:end+1] and sims are in sims[start:end].
        """
        n_sentences = end - start + 1  # add 1 since there is one more sent
        # If number of sentences is small enough, don't split
        if self.max_sents is None or n_sentences <= self.max_sents:
            return []
        # If number of sentences is too small, return as whole
        if n_sentences <= self.min_sents:
            return []

        # Find smallest index and split there.
        min_idx = int(sims[start:end].argmin()) + start

        left_cut_idxs: List[int] = []
        right_cut_idxs: List[int] = []
        # Recursively split the two branches.
        if min_idx != start:
            left_cut_idxs = self._balance_chunks(sims, start, min_idx)
        if min_idx + 1 < end:
            right_cut_idxs = self._balance_chunks(sims, min_idx + 1, end)
        return left_cut_idxs + [min_idx] + right_cut_idxs

    def _chunk_single(self, text: str) -> List[str]:
        """
        Chunks the text into semantically distinct chunks.
        """
        sents = self._sentence_split(text)
        if len(sents) == 0:
            raise ValueError("Encountered empty text after splitting")

        # Merge very short sentences
        sents = _merge_to_min_length(sents, self.min_sent_length, sep=" ")

        # If already within max_sents, return as single chunk
        if self.max_sents is not None and len(sents) <= self.max_sents:
            return [' '.join(sents)]

        # Compute embeddings
        embs = self.model.encode(sents, convert_to_numpy=True)
        # Normalize
        embs = embs / np.linalg.norm(embs, axis=1, keepdims=True)
        # Compute adjacent cosine similarities
        sims = np.sum(embs[:-1] * embs[1:], axis=1).astype(np.float32)

        # sims[i] is the similarity between sents[i] and sents[i + 1]
        splits = self._balance_chunks(sims, 0, len(sims) + 1)
        splits = [-1] + splits + [len(sims)]

        # If splits[i - 1] = r (meaning sents[r] belongs to previous chunk)
        #    splits[i] = s  (meaning sents[s] belongs to this chunk)
        # then the segment is sents[r + 1: s + 1]

        chunks = []
        for start, end in pairwise(splits):
            segment = sents[start + 1: end + 1]
            chunks.append(' '.join(segment))
        return chunks
