"""
Unit tests for TextExtractor.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

# Ensure src is first for correct zataone import
src = Path(__file__).resolve().parent.parent / "src"
if str(src) not in sys.path:
    sys.path.insert(0, str(src))

import pytest

from zataone.extractors.text_extractor import TextExtractor


def make_asset(content, type="text"):
    return SimpleNamespace(
        asset_id="test-asset",
        content=content,
        type=type,
        metadata={},
    )


def test_keyword_detection():
    extractor = TextExtractor()
    asset = make_asset("This product is guaranteed to work")
    signals = extractor.extract(asset)
    assert len(signals) >= 1
    keyword_signals = [s for s in signals if s.signal_type == "keyword"]
    assert len(keyword_signals) >= 1
    assert any(s.raw_data["value"] == "guaranteed" for s in keyword_signals)


def test_percentage_pattern_detection():
    extractor = TextExtractor()
    asset = make_asset("100% effective")
    signals = extractor.extract(asset)
    percentage_signals = [s for s in signals if s.signal_type == "percentage_claim"]
    assert len(percentage_signals) >= 1
    assert percentage_signals[0].signal_type == "percentage_claim"


def test_time_pattern_detection():
    extractor = TextExtractor()
    asset = make_asset("Results in 30 days")
    signals = extractor.extract(asset)
    time_signals = [s for s in signals if s.signal_type == "time_claim"]
    assert len(time_signals) >= 1
    assert time_signals[0].signal_type == "time_claim"


def test_multiple_signals():
    extractor = TextExtractor()
    asset = make_asset("Guaranteed 100% results in 7 days")
    signals = extractor.extract(asset)
    assert len(signals) >= 3


def test_non_text_asset_ignored():
    extractor = TextExtractor()
    asset = make_asset("Guaranteed results", type="image")
    signals = extractor.extract(asset)
    assert signals == []


def test_empty_content_safe_handling():
    extractor = TextExtractor()
    asset = make_asset("")
    signals = extractor.extract(asset)
    assert signals == []
