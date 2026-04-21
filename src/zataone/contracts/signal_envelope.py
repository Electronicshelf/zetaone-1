"""
Canonical signal envelope for multimodal compliance (playbook-aligned).

Domain extractors may still use `schemas.models.Signal`; this type documents
the intended cross-domain shape and supports validation / serialization tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional

Modality = Literal["text", "image", "video", "audio"]
AnchorType = Literal["text_span", "image_bbox", "video_timerange", "audio_timerange", "none"]


@dataclass
class SignalEnvelope:
    """
    Logical signal shape shared across domains.

    Maps naturally to persisted `signals.value` JSON and API responses.
    """

    signal_id: str
    modality: Modality
    signal_type: str
    confidence: float
    extractor_id: str
    model_version: str
    value: dict[str, Any] = field(default_factory=dict)
    anchor: Optional[dict[str, Any]] = None
    anchor_type: AnchorType = "none"
