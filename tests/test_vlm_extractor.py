"""
Unit tests for VLMExtractor.
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

from zataone.extractors.vlm_extractor import VLMExtractor

# Minimal 1x1 PNG (valid image bytes)
MINIMAL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def test_text_detection():
    """Text with 'clinically proven' produces vlm_contextual_claim signal."""
    extractor = VLMExtractor()
    asset = SimpleNamespace(
        asset_id="test",
        type="text",
        content="This treatment is clinically proven",
    )
    signals = extractor.extract(asset)

    assert len(signals) >= 1
    assert signals[0].signal_type == "vlm_contextual_claim"
    assert signals[0].raw_data["matched_value"] == "clinically proven"
    assert signals[0].raw_data["modality"] == "text"


def test_image_detection():
    """Image with image_data produces signal with modality=image."""
    extractor = VLMExtractor()
    asset = SimpleNamespace(
        asset_id="test",
        type="image",
        image_data=MINIMAL_PNG,
    )
    signals = extractor.extract(asset)

    assert len(signals) >= 1
    assert signals[0].raw_data["modality"] == "image"


def test_non_supported_asset():
    """asset.type='audio' returns empty signals."""
    extractor = VLMExtractor()
    asset = SimpleNamespace(
        asset_id="test",
        type="audio",
        content="some audio",
    )
    signals = extractor.extract(asset)
    assert signals == []


def test_empty_content_safe():
    """asset.type='text' with empty content returns empty signals."""
    extractor = VLMExtractor()
    asset = SimpleNamespace(
        asset_id="test",
        type="text",
        content="",
    )
    signals = extractor.extract(asset)
    assert signals == []


def test_case_insensitive_detection():
    """'FDA APPROVED' is detected case-insensitively."""
    extractor = VLMExtractor()
    asset = SimpleNamespace(
        asset_id="test",
        type="text",
        content="FDA APPROVED treatment",
    )
    signals = extractor.extract(asset)

    assert len(signals) >= 1
    assert any(s.raw_data["matched_value"] == "FDA approved" for s in signals)
