# zataone asset model

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, ForeignKey, Column, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from zataone.storage.database import Base

if TYPE_CHECKING:
    from zataone.models.signal import Signal
    from zataone.models.evidence import Evidence
    from zataone.models.verdict import Verdict
    from zataone.models.violation import Violation


class Asset(Base):
    """Asset model - input content for compliance check."""

    __tablename__ = "assets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_assets_tenant_idempotency"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    content_hash = Column(String(64), nullable=False)
    type = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False, default="processing")
    idempotency_key = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    signals = relationship("Signal", back_populates="asset", cascade="all, delete-orphan")
    evidence = relationship("Evidence", back_populates="asset", cascade="all, delete-orphan")
    verdicts = relationship("Verdict", back_populates="asset", cascade="all, delete-orphan")
    violations = relationship("Violation", back_populates="asset", cascade="all, delete-orphan")