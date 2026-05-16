"""Regression: default flag preserves fragment-based policy behavior."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

src = Path(__file__).resolve().parent.parent / "src"
if str(src) not in sys.path:
    sys.path.insert(0, str(src))

from zataone.document.flags import document_centric_enabled
from zataone.policy_engine.engine import PolicyEngine


def test_document_centric_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ZATAONE_DOCUMENT_CENTRIC", raising=False)
    assert document_centric_enabled() is False


def test_fragment_matching_unchanged_with_full_string_signal(monkeypatch):
    monkeypatch.setenv("ZATAONE_DOCUMENT_CENTRIC", "false")
    engine = PolicyEngine()
    engine.load_policy_pack(
        rules={
            "misleading_exaggerated_claims": {
                "name": "Misleading Claims",
                "prohibited_terms": ["guaranteed"],
                "severity": "HIGH",
            },
        }
    )
    sig = SimpleNamespace(
        signal_id="sig-001",
        signal_type="keyword",
        confidence=0.9,
        raw_data={"text": "This product is guaranteed to work", "type": "ocr_text"},
    )
    violations = engine.evaluate([sig])
    assert len(violations) >= 1
    assert violations[0].signal_id == "sig-001"
    assert violations[0].evidence_data.get("document_centric") is not True


def test_verdict_metadata_document_shape(monkeypatch):
    """Verdict metadata shape produced by pipeline document attachment step."""
    monkeypatch.setenv("ZATAONE_DOCUMENT_CENTRIC", "false")
    from zataone.document.builder import DocumentBuilder
    from zataone.document.flags import document_centric_enabled

    asset = SimpleNamespace(
        type="text",
        content="guaranteed results",
        asset_id="test-asset",
        metadata={},
    )
    document = DocumentBuilder.build(asset, [])
    metadata = {
        "document": document.to_dict(),
        "document_centric_enabled": document_centric_enabled(),
    }
    assert "normalized_text" in metadata["document"]
    assert "guaranteed" in metadata["document"]["normalized_text"].lower()
    assert metadata["document_centric_enabled"] is False
