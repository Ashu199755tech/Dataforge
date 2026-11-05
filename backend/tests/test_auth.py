from backend.app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    encrypt_secret,
    decrypt_secret,
    mask_secret_dict
)


def test_password_hashing():
    pw = "SuperSecurePassword123!"
    hashed = get_password_hash(pw)
    assert verify_password(pw, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_token_creation():
    token = create_access_token({"sub": "user_123", "role": "Admin"})
    assert isinstance(token, str)
    assert len(token) > 20


def test_secret_encryption_and_masking():
    creds = {
        "host": "db.corp.internal",
        "port": 5432,
        "user": "etl_service",
        "password": "SecretDBPassword!#$",
        "api_key": "sk_live_9999"
    }
    encrypted = encrypt_secret(creds)
    assert encrypted != str(creds)

    decrypted = decrypt_secret(encrypted)
    assert decrypted["password"] == "SecretDBPassword!#$"
    assert decrypted["user"] == "etl_service"

    masked = mask_secret_dict(decrypted)
    assert masked["password"] == "********"
    assert masked["api_key"] == "********"
    assert masked["user"] == "etl_service"
    assert masked["host"] == "db.corp.internal"
