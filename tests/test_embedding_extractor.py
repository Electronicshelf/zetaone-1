"""
Unit tests for EmbeddingExtractor.
Pure extractor tests; no database or ML libraries.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

# Ensure src is first for correct zataone import
src = Path(__file__).resolve().parent.parent / "src"
if str(src) not in sys.path:
    sys.path.insert(0, str(src))

from zataone.extractors.embedding_extractor import EmbeddingExtractor


def make_asset(content, type="text"):
    return SimpleNamespace(
        asset_id="test-asset",
        content=content,
        type=type,
        metadata={},
    )


def test_medical_claim_detection():
    """Content with medical claim phrase produces semantic_claim signal."""
    extractor = EmbeddingExtractor()
    asset = make_asset("This product can heal your condition")
    signals = extractor.extract(asset)

    assert len(signals) >= 1
    semantic_signals = [s for s in signals if s.signal_type == "semantic_claim"]
    assert len(semantic_signals) >= 1
    assert semantic_signals[0].raw_data["category"] == "medical_claim"
    assert semantic_signals[0].raw_data["matched_value"] == "heal"
    assert semantic_signals[0].source_model == "embedding_extractor"
    assert semantic_signals[0].raw_data["source"] == "embedding_stub"


def test_guarantee_claim_detection():
    """Content with guarantee claim phrase produces semantic_claim signal."""
    extractor = EmbeddingExtractor()
    asset = make_asset("We offer guaranteed results")
    signals = extractor.extract(asset)

    assert len(signals) >= 1
    semantic_signals = [s for s in signals if s.signal_type == "semantic_claim"]
    assert len(semantic_signals) >= 1
    assert semantic_signals[0].raw_data["category"] == "guarantee_claim"
    assert semantic_signals[0].raw_data["matched_value"] == "guaranteed results"


def test_non_text_asset_ignored():
    """asset.type != 'text' returns empty signals."""
    extractor = EmbeddingExtractor()
    asset = make_asset("heal treat diagnose", type="image")
    signals = extractor.extract(asset)
    assert signals == []


def test_missing_content_returns_empty():
    """Empty or missing content returns empty signals."""
    extractor = EmbeddingExtractor()
    asset = make_asset("")
    signals = extractor.extract(asset)
    assert signals == []


def test_multiple_signals():
    """Content with both medical and guarantee claims produces multiple signals."""
    extractor = EmbeddingExtractor()
    asset = make_asset("Clinically proven to treat pain with no side effects")
    signals = extractor.extract(asset)

    assert len(signals) >= 2
    categories = [s.raw_data["category"] for s in signals]
    assert "medical_claim" in categories
    assert "guarantee_claim" in categories


def test_case_insensitive():
    """Matching is case-insensitive."""
    extractor = EmbeddingExtractor()
    asset = make_asset("CLINICALLY PROVEN and ZERO RISK")
    signals = extractor.extract(asset)

    assert len(signals) >= 2
    matched = [s.raw_data["matched_value"] for s in signals]
    assert "clinically proven" in matched
    assert "zero risk" in matched
