"""
OCR extractor — thin domain wrapper over zataone.extractors.modality.ocr.
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime
from typing import Any, List

parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

_zataone_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_src_root = os.path.dirname(_zataone_dir)
if os.path.exists(os.path.join(_zataone_dir, "extractors", "base.py")):
    if _src_root not in sys.path:
        sys.path.insert(0, _src_root)

try:
    from zataone.extractors.base import BaseExtractor
except ImportError:
    from abc import ABC, abstractmethod

    class BaseExtractor(ABC):
        extractor_id: str = ""
        version: str = ""

        @abstractmethod
        def extract(self, asset):
            pass


from schemas.models import Signal, SignalType

from zataone.extractors.modality import ocr as ocr_mod
from zataone.extractors.modality.ocr import OCRBackend, TesseractOCRBackend, get_ocr_backend

# Re-export for tests / callers that need backend types
TESSERACT_AVAILABLE = ocr_mod.TESSERACT_AVAILABLE


class OCRExtractor(BaseExtractor):
    """OCR: modality backends → domain signals."""

    extractor_id = "ad_compliance_ocr"
    version = "1.0.0"

    def __init__(
        self,
        backend: OCRBackend | None = None,
        backend_type: str = "tesseract",
        min_confidence: int = 40,
    ):
        if backend is None:
            try:
                self.backend = get_ocr_backend(
                    backend_type, min_confidence=min_confidence
                )
                self.model_name = f"ocr_{self.backend.backend_name}"
            except (ImportError, ValueError):
                self.backend = None
                self.model_name = "ocr_placeholder"
        else:
            self.backend = backend
            self.model_name = f"ocr_{backend.backend_name}"

    def extract(self, asset: Any) -> List[Signal]:
        image_data = getattr(asset, "image_data", None)
        if image_data is None or self.backend is None:
            return []
        ocr_results = self.backend.extract_text_data(image_data)
        signals = []
        for ocr_result in ocr_results:
            bbox_list = ocr_result.get("bbox", [0, 0, 0, 0])
            if len(bbox_list) == 4:
                bbox = {
                    "x": float(bbox_list[0]),
                    "y": float(bbox_list[1]),
                    "width": float(bbox_list[2]),
                    "height": float(bbox_list[3]),
                }
            else:
                bbox = None
            signal = Signal(
                signal_id=str(uuid.uuid4()),
                signal_type=SignalType.TEXT,
                source_model=self.model_name,
                confidence=ocr_result.get("confidence", 0.0),
                raw_data={
                    "text": ocr_result.get("value", ""),
                    "type": ocr_result.get("type", "ocr_text"),
                    "source": ocr_result.get("source", "image"),
                    "bbox": bbox_list,
                },
                bounding_box=bbox,
                detected_at=datetime.now(),
            )
            signals.append(signal)
        return signals
