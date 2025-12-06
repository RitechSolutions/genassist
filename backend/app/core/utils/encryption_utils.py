from cryptography.fernet import Fernet
from app.core.config.settings import settings


fernet = Fernet(settings.FERNET_KEY.encode())


def encrypt_key(key: str) -> str:
    return fernet.encrypt(key.encode()).decode()


def decrypt_key(token: str) -> str:
    try:
        decrypt = fernet.decrypt(token.encode()).decode()
        print(decrypt)
        return decrypt
    except Exception as e:
        print(f"Error decrypting key: {e}")
        return token