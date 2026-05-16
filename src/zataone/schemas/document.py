# zataone unified document schemas

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


DocumentModality = Literal["text", "image", "audio", "video", "unknown"]


@dataclass
class DocumentSpan:
    """Character span in normalized_text linked to a source extractor signal."""

    start: int
    end: int
    text: str
    source_signal_id: str
    source_type: str  # ocr | asr | text | vision | timeline
    bbox: dict[str, Any] | list[Any] | None = None


@dataclass
class TimelineEntry:
    """Future-ready video timeline segment."""

    timestamp_sec: float
    text: str
    source_signal_ids: list[str] = field(default_factory=list)


@dataclass
class DocumentSignal:
    """
    Unified semantic document for policy evaluation and explainability.
    One per asset per pipeline run.
    """

    asset_id: str | None
    modality: DocumentModality
    normalized_text: str
    source_signal_ids: list[str] = field(default_factory=list)
    spans: list[DocumentSpan] = field(default_factory=list)
    scene_descriptions: list[str] = field(default_factory=list)
    timeline: list[TimelineEntry] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable snapshot for verdict metadata and graph API."""
        d = asdict(self)
        d["spans"] = [asdict(s) for s in self.spans]
        d["timeline"] = [asdict(t) for t in self.timeline]
        return d
