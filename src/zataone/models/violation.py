# zataone violation model

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Float, ForeignKey, Column, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import relationship

from zataone.storage.database import Base

if TYPE_CHECKING:
    from zataone.models.asset import Asset
    from zataone.models.evidence import Evidence
    from zataone.models.signal import Signal


class Violation(Base):
    """Violation model - explicit storage of rule violations linked to asset and signal."""

    __tablename__ = "violations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id = Column(
        UUID(as_uuid=True),
        ForeignKey("assets.id"),
        nullable=False,
        index=True,
    )
    signal_id = Column(
        UUID(as_uuid=True),
        ForeignKey("signals.id"),
        nullable=False,
        index=True,
    )
    rule_id = Column(String(128), nullable=False, index=True)
    violation_type = Column(String(64), nullable=False, index=True)
    severity = Column(Float, nullable=True)
    evidence_data = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    asset = relationship("Asset", back_populates="violations")
    signal = relationship("Signal", back_populates="violations")
    evidence = relationship("Evidence", back_populates="violation", cascade="all, delete-orphan")
