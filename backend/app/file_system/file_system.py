import os

from app import settings


def ensure_directories():
    os.makedirs(settings.RECORDINGS_DIR , exist_ok=True)
