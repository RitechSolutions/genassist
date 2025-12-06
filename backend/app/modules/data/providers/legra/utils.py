import logging
import sys

from sentence_transformers import SentenceTransformer


def get_logger(name: str) -> logging.Logger:
    """
    Returns a logger configured to print to stdout with a standard format.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        fmt = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
        handler.setFormatter(logging.Formatter(fmt))
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)
    return logger


def load_sentence_transformer(model_name: str) -> SentenceTransformer:
    """
    Wrapper around SentenceTransformer to handle caching or customization in
    future.
    """
    return SentenceTransformer(model_name)
