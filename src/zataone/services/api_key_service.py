# zataone API key service

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from zataone.models.api_key import APIKey

_KEY_PREFIX = "zta_"


def _generate_raw_key() -> str:
    """Generate a raw API key — shown once, never stored."""
    return _KEY_PREFIX + secrets.token_urlsafe(32)


def _hash_key(raw_key: str) -> str:
    """SHA-256 hex digest of the raw key."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def _key_prefix(raw_key: str) -> str:
    """First 12 characters of the raw key (safe to display)."""
    return raw_key[:12]


class APIKeyService:
    """Create, validate, and revoke API keys."""

    def create_key(
        self,
        session: Session,
        tenant_id: uuid.UUID | str,
        name: str,
        expires_at: datetime | None = None,
    ) -> tuple[str, APIKey]:
        """
        Create a new API key for a tenant.

        Returns (raw_key, record). raw_key is shown once — caller must deliver it
        to the tenant immediately; it cannot be recovered from the DB.
        """
        raw_key = _generate_raw_key()
        record = APIKey(
            tenant_id=uuid.UUID(str(tenant_id)),
            key_hash=_hash_key(raw_key),
            prefix=_key_prefix(raw_key),
            name=name,
            is_active=True,
            expires_at=expires_at,
        )
        session.add(record)
        session.flush()
        return raw_key, record

    def validate_key(
        self, session: Session, raw_key: str
    ) -> APIKey | None:
        """
        Validate a raw API key. Returns the APIKey record (with tenant_id) or None.
        Updates last_used_at on success.
        """
        if not raw_key or not raw_key.startswith(_KEY_PREFIX):
            return None
        key_hash = _hash_key(raw_key)
        record: APIKey | None = (
            session.query(APIKey)
            .filter(APIKey.key_hash == key_hash, APIKey.is_active == True)  # noqa: E712
            .first()
        )
        if record is None:
            return None
        if record.expires_at is not None and record.expires_at < datetime.utcnow():
            return None
        record.last_used_at = datetime.utcnow()
        session.flush()
        return record

    def revoke_key(self, session: Session, key_id: uuid.UUID | str) -> bool:
        """Revoke a key by ID. Returns True if found and deactivated."""
        record: APIKey | None = (
            session.query(APIKey)
            .filter(APIKey.id == uuid.UUID(str(key_id)))
            .first()
        )
        if record is None:
            return False
        record.is_active = False
        session.flush()
        return True

    def list_keys(self, session: Session, tenant_id: uuid.UUID | str) -> list[dict[str, Any]]:
        """List all keys for a tenant (never returns the hash)."""
        records = (
            session.query(APIKey)
            .filter(APIKey.tenant_id == uuid.UUID(str(tenant_id)))
            .order_by(APIKey.created_at.desc())
            .all()
        )
        return [
            {
                "id": str(r.id),
                "name": r.name,
                "prefix": r.prefix,
                "is_active": r.is_active,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "last_used_at": r.last_used_at.isoformat() if r.last_used_at else None,
                "expires_at": r.expires_at.isoformat() if r.expires_at else None,
            }
            for r in records
        ]
