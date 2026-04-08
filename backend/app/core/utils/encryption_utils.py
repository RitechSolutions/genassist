import logging

from cryptography.fernet import Fernet
from app.core.config.settings import settings

logger = logging.getLogger(__name__)

fernet = Fernet(settings.FERNET_KEY.encode())


def encrypt_key(key: str) -> str:
    return fernet.encrypt(key.encode()).decode()


def decrypt_key(token: str) -> str:
    if token is None or token == "":
        return token
    try:
        return fernet.decrypt(token.encode()).decode()
    except Exception as e:
        # Fernet fails if FERNET_KEY differs from the one used at encrypt time, or if the
        # value is corrupt. Celery workers must use the same FERNET_KEY as the API.
        logger.warning(
            "Error decrypting key: %s. If this appears during background jobs (e.g. Zendesk KB "
            "sync), verify CELERY workers load the same FERNET_KEY as the web app. "
            "After rotating FERNET_KEY, re-save affected datasource credentials.",
            e,
        )
        return token