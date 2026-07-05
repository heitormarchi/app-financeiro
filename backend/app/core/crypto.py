from cryptography.fernet import Fernet

from app.core.config import settings

_f = Fernet(settings.fernet_key.encode())


def encrypt_str(value: str) -> str:
    return _f.encrypt(value.encode()).decode()


def decrypt_str(token: str) -> str:
    return _f.decrypt(token.encode()).decode()
