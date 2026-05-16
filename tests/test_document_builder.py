"""Unit tests for unified document builder."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

src = Path(__file__).resolve().parent.parent / "src"
if str(src) not in sys.path:
    sys.path.insert(0, str(src))

from zataone.document.builder import DocumentBuilder, normalize_document_text
from zataone.schemas.document import DocumentSignal


def _ocr_signal(signal_id: str, text: str, left: int, top: int) -> SimpleNamespace:
    return SimpleNamespace(
        signal_id=signal_id,
        signal_type="text",
        confidence=0.9,
        raw_data={
            "type": "ocr_text",
            "text": text,
            "source": "image",
            "bbox": [left, top, 40, 12],
        },
        bounding_box={"x": left, "y": top, "width": 40, "height": 12},
    )


def test_normalize_document_text_collapses_whitespace():
    assert normalize_document_text("  hello   world  ") == "hello world"
    assert normalize_document_text("a\n\n\n\nb") == "a\n\nb"


def test_text_asset_uses_full_content():
    asset = SimpleNamespace(type="text", content="Guaranteed cure in 5 days", asset_id="a1")
    doc = DocumentBuilder.build(asset, [])
    assert isinstance(doc, DocumentSignal)
    assert doc.modality == "text"
    assert "guaranteed cure in 5 days" in doc.normalized_text.lower()
    assert len(doc.spans) == 1
    assert doc.spans[0].source_type == "text"


def test_ocr_aggregation_reading_order():
    asset = SimpleNamespace(type="image", image_data=b"x", asset_id="img-1")
    signals = [
        _ocr_signal("s2", "pounds", 120, 10),
        _ocr_signal("s1", "lose", 10, 10),
        _ocr_signal("s3", "in", 200, 10),
        _ocr_signal("s4", "5", 240, 10),
        _ocr_signal("s5", "days", 280, 10),
    ]
    doc = DocumentBuilder.build(asset, signals)
    assert "lose pounds in 5 days" in doc.normalized_text.lower()
    assert len(doc.spans) == 5
    assert doc.metadata["ocr_token_count"] == 5


def test_ocr_phrase_in_document_not_single_token():
    asset = SimpleNamespace(type="image", asset_id="img-2")
    signals = [
        _ocr_signal("a", "lose", 0, 0),
        _ocr_signal("b", "10", 50, 0),
        _ocr_signal("c", "pounds", 90, 0),
        _ocr_signal("d", "in", 160, 0),
        _ocr_signal("e", "5", 200, 0),
        _ocr_signal("f", "days", 230, 0),
    ]
    doc = DocumentBuilder.build(asset, signals)
    joined = doc.normalized_text.lower()
    assert "lose" in joined and "pounds" in joined and "days" in joined


def test_asr_full_transcript():
    asset = SimpleNamespace(type="audio", audio_data=b"wav", asset_id="aud-1")
    signals = [
        SimpleNamespace(
            signal_id="asr-1",
            signal_type="text",
            confidence=0.95,
            raw_data={
                "type": "asr_text",
                "text": "We guaranteed results overnight",
                "source": "audio",
            },
        )
    ]
    doc = DocumentBuilder.build(asset, signals)
    assert "guaranteed results overnight" in doc.normalized_text.lower()
    assert any(s.source_type == "asr" for s in doc.spans)


def test_vision_scene_descriptions():
    asset = SimpleNamespace(type="image", asset_id="img-3")
    signals = [
        SimpleNamespace(
            signal_id="v1",
            signal_type="object",
            confidence=0.88,
            raw_data={
                "type": "vision_object",
                "label": "syringe",
                "confidence": 0.88,
                "bbox": [1, 2, 3, 4],
                "model": "grounding_dino",
            },
        ),
        SimpleNamespace(
            signal_id="v2",
            signal_type="object",
            confidence=0.75,
            raw_data={
                "type": "vision_object",
                "label": "cash",
                "confidence": 0.75,
                "bbox": [5, 6, 7, 8],
                "model": "grounding_dino",
            },
        ),
    ]
    doc = DocumentBuilder.build(asset, signals)
    assert len(doc.scene_descriptions) == 1
    assert "syringe" in doc.scene_descriptions[0].lower()
    assert "cash" in doc.scene_descriptions[0].lower()
    assert "image contains" in doc.normalized_text.lower()


def test_timeline_future_ready():
    asset = SimpleNamespace(type="video", asset_id="vid-1")
    signals = [
        SimpleNamespace(
            signal_id="t1",
            signal_type="text",
            confidence=1.0,
            raw_data={
                "type": "timeline_text",
                "timestamp_sec": 3.0,
                "text": 'text overlay: "Guaranteed cure"',
            },
        ),
    ]
    doc = DocumentBuilder.build(asset, signals)
    assert len(doc.timeline) == 1
    assert doc.timeline[0].timestamp_sec == 3.0
    assert "[00:03]" in doc.normalized_text


def test_document_to_dict_serializable():
    asset = SimpleNamespace(type="text", content="hello", asset_id="x")
    doc = DocumentBuilder.build(asset, [])
    d = doc.to_dict()
    assert d["modality"] == "text"
    assert "normalized_text" in d
    assert "spans" in d
