"""
Domain-agnostic OCR (Tesseract via pytesseract). Thresholds are constructor args.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from io import BytesIO
from typing import Any

try:
    import pytesseract
    from PIL import Image

    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False


class OCRBackend(ABC):
    """Abstract OCR backend."""

    @abstractmethod
    def extract_text_data(self, image_data: bytes) -> list[dict[str, Any]]:
        """Return list of dicts: type, value, confidence, source, bbox [L,T,W,H]."""
        raise NotImplementedError


class TesseractOCRBackend(OCRBackend):
    """Tesseract via pytesseract. min_confidence is Tesseract 0–100 scale."""

    def __init__(self, min_confidence: int = 40):
        if not TESSERACT_AVAILABLE:
            raise ImportError(
                "pytesseract and Pillow are required. Install with: pip install pytesseract pillow"
            )
        self.backend_name = "tesseract"
        self._min_confidence = int(min_confidence)

    def extract_text_data(self, image_data: bytes) -> list[dict[str, Any]]:
        image = Image.open(BytesIO(image_data))
        ocr_data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        results: list[dict[str, Any]] = []
        num_detections = len(ocr_data.get("text", []))
        for i in range(num_detections):
            text = ocr_data.get("text", [])[i]
            conf = ocr_data.get("conf", [])[i]
            left = ocr_data.get("left", [])[i]
            top = ocr_data.get("top", [])[i]
            width = ocr_data.get("width", [])[i]
            height = ocr_data.get("height", [])[i]
            if not text or not str(text).strip():
                continue
            if conf == -1 or conf < self._min_confidence:
                continue
            normalized_confidence = float(conf) / 100.0
            results.append(
                {
                    "type": "ocr_text",
                    "value": str(text).strip(),
                    "confidence": normalized_confidence,
                    "source": "image",
                    "bbox": [int(left), int(top), int(width), int(height)],
                }
            )
        return results


def get_ocr_backend(backend_type: str = "tesseract", *, min_confidence: int = 40) -> OCRBackend:
    """Factory for OCR backends. Same pattern for every domain; tune via YAML."""
    if backend_type == "tesseract":
        return TesseractOCRBackend(min_confidence=min_confidence)
    if backend_type == "google_vision":
        raise ValueError("Google Vision backend not yet implemented")
    raise ValueError(f"Unsupported OCR backend type: {backend_type}")
