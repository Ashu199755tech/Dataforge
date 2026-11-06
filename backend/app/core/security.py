from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from jose import jwt
import bcrypt
from cryptography.fernet import Fernet
from backend.app.core.config import settings
import base64
import hashlib
import json

# Derive a valid 32-byte urlsafe base64 key for Fernet from settings.ENCRYPTION_KEY
raw_key = settings.ENCRYPTION_KEY.encode()
hasher = hashlib.sha256(raw_key).digest()
fernet_key = base64.urlsafe_b64encode(hasher)
cipher_suite = Fernet(fernet_key)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    # bcrypt limits to 72 bytes
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def create_access_token(data: Dict[str, Any], expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def encrypt_secret(secret_data: Dict[str, Any]) -> str:
    """Encrypts a dict (e.g., credentials) into an AES-256 Fernet token."""
    serialized = json.dumps(secret_data).encode("utf-8")
    return cipher_suite.encrypt(serialized).decode("utf-8")


def decrypt_secret(encrypted_token: str) -> Dict[str, Any]:
    """Decrypts a token back into credentials dict."""
    if not encrypted_token:
        return {}
    try:
        decrypted = cipher_suite.decrypt(encrypted_token.encode("utf-8"))
        return json.loads(decrypted.decode("utf-8"))
    except Exception:
        # Graceful fallback if stored as plaintext or encrypted under another key
        try:
            return json.loads(encrypted_token)
        except Exception:
            return {}


def mask_secret_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """Replaces sensitive keys with asterisks, handling nested structures recursively."""
    if not isinstance(data, dict):
        return data
    masked = {}
    sensitive_keys = {
        "password", "secret", "token", "api_key", "private_key",
        "access_key", "account_key", "sas_token", "credential",
        "service_account", "private_key_id", "client_secret",
        "connection_string", "session_token"
    }
    for k, v in data.items():
        if isinstance(v, dict):
            masked[k] = mask_secret_dict(v)
        elif any(s in str(k).lower() for s in sensitive_keys):
            masked[k] = "********"
        else:
            masked[k] = v
    return masked
