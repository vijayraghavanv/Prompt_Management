import os
import base64
from cryptography.fernet import Fernet, InvalidToken
from app.core.config import settings


def pad_base64(key: str) -> str:
    """Add padding to base64 string if needed"""
    padding = 4 - (len(key) % 4)
    if padding != 4:
        return key + ("=" * padding)
    return key


def get_encryption_key() -> bytes:
    """
    Get or generate Fernet encryption key
    
    The key should be set in environment variables. If not found,
    generates a new one and prints it (for first time setup).
    """
    try:
        # Try to use existing key
        key = settings.FERNET_KEY.strip()
        # Handle URL-safe base64 by replacing - and _
        key = key.replace("-", "+").replace("_", "/")
        # Add padding if needed
        key = pad_base64(key)
        # Validate the key
        base64.b64decode(key)
        return key.encode()
    except Exception as e:
        print(f"Invalid Fernet key: {str(e)}")
        # Generate new key if invalid
        key = Fernet.generate_key()
        print(f"Generated new Fernet key: {key.decode()}")
        print("Please set this as FERNET_KEY in your .env file")
        return key


_fernet = None

def get_fernet() -> Fernet:
    """Get Fernet instance using encryption key"""
    global _fernet
    if _fernet is None:
        _fernet = Fernet(get_encryption_key())
    return _fernet


def encrypt_value(value: str) -> str:
    """Encrypt a string value"""
    if not value:
        return ""
    try:
        return get_fernet().encrypt(value.encode()).decode()
    except Exception as e:
        print(f"Encryption error: {str(e)}")
        raise


def decrypt_value(encrypted_value: str) -> str:
    """Decrypt an encrypted string value"""
    if not encrypted_value:
        return ""
    try:
        return get_fernet().decrypt(encrypted_value.encode()).decode()
    except InvalidToken:
        print("Failed to decrypt: Invalid token. This could mean the encryption key has changed.")
        raise
    except Exception as e:
        print(f"Decryption error: {str(e)}")
        raise
