from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from cryptography.fernet import Fernet
from backend.app.core.config import settings
from backend.app.models.security import SecretVaultEntry
from backend.app.core.audit import record_audit


class BaseSecretVault(ABC):
    @abstractmethod
    def store_secret(self, name: str, value: str, description: Optional[str], db: Session, user_id: Optional[str]) -> SecretVaultEntry:
        pass

    @abstractmethod
    def get_secret(self, name: str, db: Session) -> Optional[str]:
        pass

    @abstractmethod
    def list_secrets(self, db: Session) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def delete_secret(self, name: str, db: Session, user_id: Optional[str]) -> bool:
        pass

    @abstractmethod
    def rotate_keys(self, new_encryption_key: str, db: Session, user_id: Optional[str]) -> int:
        pass


class FernetSecretVault(BaseSecretVault):
    """
    AES-256 Fernet implementation of Enterprise Secret Vault.
    Guarantees secrets are encrypted at rest with zero plaintext leaks in API.
    """

    def __init__(self, key: Optional[str] = None):
        import base64
        import hashlib
        raw_key = (key or getattr(settings, "ENCRYPTION_KEY", settings.SECRET_KEY)).encode("utf-8")
        hasher = hashlib.sha256(raw_key).digest()
        self.fernet_key = base64.urlsafe_b64encode(hasher)
        self.cipher = Fernet(self.fernet_key)

    def _derive_fernet_key(self, raw_str: str) -> bytes:
        import base64
        import hashlib
        hasher = hashlib.sha256(raw_str.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(hasher)

    def store_secret(
        self,
        name: str,
        value: str,
        description: Optional[str] = None,
        db: Session = None,
        user_id: Optional[str] = None
    ) -> SecretVaultEntry:
        encrypted_bytes = self.cipher.encrypt(value.encode("utf-8"))
        encrypted_str = encrypted_bytes.decode("utf-8")

        entry = db.query(SecretVaultEntry).filter(SecretVaultEntry.name == name).first()
        if entry:
            entry.encrypted_value = encrypted_str
            entry.description = description or entry.description
            entry.updated_at = datetime.now(timezone.utc)
            action = "SECRET_UPDATE"
        else:
            entry = SecretVaultEntry(
                name=name,
                description=description,
                encrypted_value=encrypted_str,
                vault_provider="AES-256-Fernet",
                created_by_id=user_id
            )
            db.add(entry)
            action = "SECRET_CREATE"

        db.commit()
        db.refresh(entry)

        record_audit(
            db=db,
            action=action,
            resource_type="Secret",
            resource_id=entry.id,
            details={"name": name, "vault_provider": entry.vault_provider},
            user_id=user_id
        )
        return entry

    def get_secret(self, name: str, db: Session) -> Optional[str]:
        """Internal retrieval for activities and connector credentials."""
        entry = db.query(SecretVaultEntry).filter(SecretVaultEntry.name == name).first()
        if not entry:
            return None
        decrypted_bytes = self.cipher.decrypt(entry.encrypted_value.encode("utf-8"))
        return decrypted_bytes.decode("utf-8")

    def list_secrets(self, db: Session) -> List[Dict[str, Any]]:
        """Returns metadata list with masked secrets."""
        entries = db.query(SecretVaultEntry).order_by(SecretVaultEntry.name.asc()).all()
        return [
            {
                "id": e.id,
                "name": e.name,
                "description": e.description,
                "vault_provider": e.vault_provider,
                "is_masked": True,
                "created_at": e.created_at.isoformat() if e.created_at else None,
                "updated_at": e.updated_at.isoformat() if e.updated_at else None,
            }
            for e in entries
        ]

    def delete_secret(self, name: str, db: Session, user_id: Optional[str] = None) -> bool:
        entry = db.query(SecretVaultEntry).filter(SecretVaultEntry.name == name).first()
        if not entry:
            return False
        secret_id = entry.id
        db.delete(entry)
        db.commit()

        record_audit(
            db=db,
            action="SECRET_DELETE",
            resource_type="Secret",
            resource_id=secret_id,
            details={"name": name},
            user_id=user_id
        )
        return True

    def rotate_keys(self, new_key_raw: str, db: Session, user_id: Optional[str] = None) -> int:
        """Re-encrypts all vault secrets with new key without service interruption."""
        new_fernet_key = self._derive_fernet_key(new_key_raw)
        new_cipher = Fernet(new_fernet_key)

        entries = db.query(SecretVaultEntry).all()
        count = 0
        for entry in entries:
            decrypted = self.cipher.decrypt(entry.encrypted_value.encode("utf-8"))
            re_encrypted = new_cipher.encrypt(decrypted)
            entry.encrypted_value = re_encrypted.decode("utf-8")
            entry.updated_at = datetime.now(timezone.utc)
            count += 1

        db.commit()
        # Update current cipher
        self.cipher = new_cipher
        self.fernet_key = new_fernet_key

        record_audit(
            db=db,
            action="SECRET_KEY_ROTATE",
            resource_type="SecretVault",
            resource_id="global_vault",
            details={"rotated_entries": count},
            user_id=user_id
        )
        return count


# Singleton secret vault instance
secret_vault = FernetSecretVault()
