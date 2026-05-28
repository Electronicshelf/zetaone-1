# zataone API key model

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from zataone.storage.database import Base


class APIKey(Base):
    """Hashed API key bound to a tenant. Raw key is shown once at creation and never stored."""

    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    # SHA-256 hex of the raw key — raw key is never persisted.
    key_hash = Column(String(64), nullable=False, unique=True, index=True)
    # First 8 chars of raw key for display (safe to store, not enough to reconstruct).
    prefix = Column(String(12), nullable=False)
    name = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
