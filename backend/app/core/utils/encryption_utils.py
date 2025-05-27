from cryptography.fernet import Fernet
from app.core.config.settings import settings


fernet = Fernet(settings.FERNET_KEY.encode())


def encrypt_key(key: str) -> str:
    return fernet.encrypt(key.encode()).decode()


def decrypt_key(token: str) -> str:
    return fernet.decrypt(token.encode()).decode()
