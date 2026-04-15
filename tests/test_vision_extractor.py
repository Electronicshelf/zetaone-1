"""
Unit tests for VisionExtractor.
Pure extractor tests; no database or ML libraries.
"""

import base64
import sys
from pathlib import Path
from types import SimpleNamespace

# Ensure src is first for correct zataone import
src = Path(__file__).resolve().parent.parent / "src"
if str(src) not in sys.path:
    sys.path.insert(0, str(src))

from zataone.extractors.vision_extractor import VisionExtractor

# Minimal 1x1 PNG (valid image bytes)
MINIMAL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def test_valid_image_produces_signals():
    """Valid image with image_data produces visual_indicator signals."""
    extractor = VisionExtractor()
    asset = SimpleNamespace(
        asset_id="test",
        type="image",
        image_data=MINIMAL_PNG,
    )
    signals = extractor.extract(asset)

    assert len(signals) >= 1
    visual_signals = [s for s in signals if s.signal_type == "visual_indicator"]
    assert len(visual_signals) >= 1
    assert visual_signals[0].source_model == "vision_extractor"
    assert visual_signals[0].raw_data["source"] == "vision_stub"


def test_non_image_asset_ignored():
    """asset.type='text' - expect empty signals."""
    extractor = VisionExtractor()
    asset = SimpleNamespace(
        asset_id="test",
        type="text",
        content="hello",
    )
    signals = extractor.extract(asset)
    assert signals == []


def test_missing_image_data_safe_handling():
    """asset.type='image' but image_data=None - expect empty signals, no exception."""
    extractor = VisionExtractor()
    asset = SimpleNamespace(
        asset_id="test",
        type="image",
        image_data=None,
    )
    signals = extractor.extract(asset)
    assert signals == []


def test_base64_image_support():
    """asset.content with base64-encoded PNG produces signals."""
    extractor = VisionExtractor()
    base64_png = base64.b64encode(MINIMAL_PNG).decode("ascii")
    asset = SimpleNamespace(
        asset_id="test",
        type="image",
        content=base64_png,
    )
    signals = extractor.extract(asset)

    assert len(signals) >= 1
    assert any(s.signal_type == "visual_indicator" for s in signals)
    assert any(s.raw_data["source"] == "vision_stub" for s in signals)
