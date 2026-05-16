"""Policy engine document-centric matching tests."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

src = Path(__file__).resolve().parent.parent / "src"
if str(src) not in sys.path:
    sys.path.insert(0, str(src))

from zataone.document.builder import DocumentBuilder
from zataone.policy_engine.engine import PolicyEngine
from zataone.schemas.document import DocumentSignal


def _ocr_token(signal_id: str, text: str) -> SimpleNamespace:
    return SimpleNamespace(
        signal_id=signal_id,
        signal_type="text",
        confidence=0.9,
        raw_data={"type": "ocr_text", "text": text, "source": "image", "bbox": [0, 0, 10, 10]},
    )


@pytest.fixture
def misleading_rule_pack():
    engine = PolicyEngine()
    engine.load_policy_pack(
        rules={
            "misleading_exaggerated_claims": {
                "name": "Misleading Claims",
                "prohibited_terms": ["guaranteed"],
                "patterns": [
                    {
                        "pattern": r"lose\s+\d+\s+pounds?\s+in\s+\d+\s+days?",
                        "confidence": 0.95,
                    }
                ],
                "severity": "HIGH",
            },
        }
    )
    return engine


def test_document_centric_matches_phrase_across_ocr_tokens(monkeypatch, misleading_rule_pack):
    monkeypatch.setenv("ZATAONE_DOCUMENT_CENTRIC", "true")
    asset = SimpleNamespace(type="image", asset_id="img-1")
    signals = [
        _ocr_token("t1", "lose"),
        _ocr_token("t2", "10"),
        _ocr_token("t3", "pounds"),
        _ocr_token("t4", "in"),
        _ocr_token("t5", "5"),
        _ocr_token("t6", "days"),
    ]
    document = DocumentBuilder.build(asset, signals)
    violations = misleading_rule_pack.evaluate(signals, document=document)
    assert len(violations) >= 1
    assert violations[0].rule_id == "misleading_exaggerated_claims"
    assert violations[0].evidence_data.get("document_centric") is True
    assert violations[0].evidence_data.get("matched_span") is not None


def test_fragment_mode_misses_phrase_on_single_token(monkeypatch, misleading_rule_pack):
    monkeypatch.setenv("ZATAONE_DOCUMENT_CENTRIC", "false")
    signals = [
        _ocr_token("t1", "lose"),
        _ocr_token("t2", "10"),
        _ocr_token("t3", "pounds"),
        _ocr_token("t4", "in"),
        _ocr_token("t5", "5"),
        _ocr_token("t6", "days"),
    ]
    document = DocumentBuilder.build(SimpleNamespace(type="image"), signals)
    violations = misleading_rule_pack.evaluate(signals, document=document)
  # fragment mode ignores document
    assert len(violations) == 0


def test_document_centric_medical_context_on_full_text(monkeypatch):
    monkeypatch.setenv("ZATAONE_DOCUMENT_CENTRIC", "true")
    engine = PolicyEngine()
    engine.load_policy_pack(
        rules={
            "medical_health_claims": {
                "name": "Medical",
                "context_terms": ["pain", "chronic"],
                "prohibited_terms": ["cure"],
                "severity": "HIGH",
            },
        }
    )
    document = DocumentSignal(
        asset_id="t1",
        modality="text",
        normalized_text="Heal chronic back pain fast with our cure",
        source_signal_ids=["sig-1"],
        spans=[],
    )
    violations = engine.evaluate([], document=document)
    assert len(violations) >= 1
    assert violations[0].rule_id == "medical_health_claims"
    span = violations[0].evidence_data.get("matched_span")
    assert span is not None
    assert "cure" in str(span.get("text", "")).lower()
