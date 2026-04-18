"""
Unit tests for OCRExtractor.
Mocks pytesseract; no real OCR or pytesseract installation required.
"""

import base64
import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

# Minimal stub module (MagicMock alone breaks importlib / pytest.importorskip for pytesseract)
_pytesseract_stub = ModuleType("pytesseract")
_pytesseract_stub.__spec__ = importlib.util.spec_from_loader("pytesseract", loader=None)
_pytesseract_stub.image_to_string = MagicMock(return_value="")
sys.modules["pytesseract"] = _pytesseract_stub

# Ensure src is first for correct zataone import
src = Path(__file__).resolve().parent.parent / "src"
if str(src) not in sys.path:
    sys.path.insert(0, str(src))

from zataone.extractors.ocr_extractor import OCRExtractor

# Minimal 1x1 PNG (valid image bytes for PIL)
MINIMAL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def test_keyword_detection():
    """Mock OCR returns 'Guaranteed instant cure' - expect ocr_keyword signals."""
    extractor = OCRExtractor()
    asset = SimpleNamespace(
        asset_id="test",
        type="image",
        image_data=MINIMAL_PNG,
    )

    with patch("pytesseract.image_to_string", return_value="Guaranteed instant cure"):
        signals = extractor.extract(asset)

    assert len(signals) >= 3
    keyword_signals = [s for s in signals if s.signal_type == "ocr_keyword"]
    assert len(keyword_signals) >= 1
    matched_values = [s.raw_data["matched_value"] for s in keyword_signals]
    assert "guaranteed" in matched_values
    assert "instant" in matched_values
    assert "cure" in matched_values


def test_percentage_detection():
    """Mock OCR returns '100% effective' - expect ocr_percentage_claim signal."""
    extractor = OCRExtractor()
    asset = SimpleNamespace(
        asset_id="test",
        type="image",
        image_data=MINIMAL_PNG,
    )

    with patch("pytesseract.image_to_string", return_value="100% effective"):
        signals = extractor.extract(asset)

    percentage_signals = [s for s in signals if s.signal_type == "ocr_percentage_claim"]
    assert len(percentage_signals) >= 1
    assert percentage_signals[0].raw_data["matched_value"] == "100%"


def test_time_claim_detection():
    """Mock OCR returns 'Results in 5 days' - expect ocr_time_claim signal."""
    extractor = OCRExtractor()
    asset = SimpleNamespace(
        asset_id="test",
        type="image",
        image_data=MINIMAL_PNG,
    )

    with patch("pytesseract.image_to_string", return_value="Results in 5 days"):
        signals = extractor.extract(asset)

    time_signals = [s for s in signals if s.signal_type == "ocr_time_claim"]
    assert len(time_signals) >= 1
    assert "5 days" in time_signals[0].raw_data["matched_value"]


def test_non_image_asset_ignored():
    """asset.type='text' - expect empty signals."""
    extractor = OCRExtractor()
    asset = SimpleNamespace(
        asset_id="test",
        type="text",
        image_data=MINIMAL_PNG,
    )
    signals = extractor.extract(asset)
    assert signals == []


def test_missing_image_data_safe_handling():
    """asset.type='image' but image_data=None - expect empty signals."""
    extractor = OCRExtractor()
    asset = SimpleNamespace(
        asset_id="test",
        type="image",
        image_data=None,
    )
    signals = extractor.extract(asset)
    assert signals == []


def test_ocr_failure_safe_handling():
    """Mock pytesseract.image_to_string to raise - expect empty signals, no exception."""
    extractor = OCRExtractor()
    asset = SimpleNamespace(
        asset_id="test",
        type="image",
        image_data=MINIMAL_PNG,
    )

    with patch("pytesseract.image_to_string", side_effect=Exception("OCR failed")):
        signals = extractor.extract(asset)

    assert signals == []
