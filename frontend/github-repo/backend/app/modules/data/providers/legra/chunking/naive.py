from typing import List

import nltk
from langchain.text_splitter import RecursiveCharacterTextSplitter

from .base import Chunker

nltk.download("punkt", quiet=True)

__all__ = ['SentenceChunker', 'CharChunker', 'RecursiveChunker']


class SentenceChunker(Chunker):
    """
    A naive chunker that splits text into fixed-size sentence chunks. E.g.,
    every `chunk_size` sentences become one chunk.

    Args:
        chunk_size: Number of sentences in a chunk.
    """

    def __init__(self, chunk_size: int = 10):
        if chunk_size < 1:
            raise ValueError("chunk_size must be >= 1")
        self.chunk_size = chunk_size

    @staticmethod
    def _sentence_split(text: str) -> List[str]:
        return nltk.tokenize.sent_tokenize(text)

    def _chunk_single(self, text: str) -> List[str]:
        sents = self._sentence_split(text)
        chunks: List[str] = []

        for i in range(0, len(sents), self.chunk_size):
            chunk = " ".join(sents[i: i + self.chunk_size])
            chunks.append(chunk)
        return chunks


class CharChunker(Chunker):
    """
    A naive chunker that splits text into chunks of some max number of
    characters.

    Args:
        max_chars: Maximum number of characters in a chunk.
    """

    def __init__(self, max_chars: int = 1200):
        if max_chars < 1:
            raise ValueError("max_chars must be >= 1")
        self.max_chars = max_chars

    def _chunk_single(self, text: str) -> List[str]:
        chunks: List[str] = []
        for i in range(0, len(text), self.max_chars):
            chunks.append(text[i: i + self.max_chars])
        return chunks


class RecursiveChunker(Chunker):
    """
    A chunker that does recursive splits.
    """

    def __init__(self, chunk_size: int = 256, chunk_overlap: int = 20, **kwargs):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            **kwargs,
        )

    def _chunk_single(self, text: str) -> List[str]:
        chunks = self.text_splitter.create_documents([text])
        return [c.page_content for c in chunks]
