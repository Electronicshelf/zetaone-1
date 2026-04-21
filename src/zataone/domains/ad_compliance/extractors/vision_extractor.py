"""
Vision extractor — thin domain wrapper over zataone.extractors.modality.vision (Grounding DINO).
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime
from typing import Any, List, Optional

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

from zataone.extractors.modality import vision as vision_mod

GROUNDING_DINO_AVAILABLE = vision_mod.GROUNDING_DINO_AVAILABLE


class VisionExtractor(BaseExtractor):
    """Grounding DINO: modality detection → domain signals."""

    extractor_id = "ad_compliance_vision"
    version = "1.0.0"

    def __init__(
        self,
        object_queries: Optional[List[str]] = None,
        model_id: Optional[str] = None,
        detection_threshold: Optional[float] = None,
        text_threshold: Optional[float] = None,
        box_score_min: Optional[float] = None,
        device: str = "cpu",
    ):
        self.model_name = "grounding_dino"
        self._object_queries = object_queries or [
            "weapon",
            "gun",
            "knife",
            "pill",
            "medicine",
            "syringe",
            "money",
            "cash",
            "banknote",
        ]
        self._model_id = model_id or "IDEA-Research/grounding-dino-base"
        self._detection_threshold = 0.3 if detection_threshold is None else float(detection_threshold)
        self._text_threshold = 0.3 if text_threshold is None else float(text_threshold)
        self._box_score_min = 0.3 if box_score_min is None else float(box_score_min)
        self._device = device

    def extract(self, asset: Any) -> List[Signal]:
        image_data = getattr(asset, "image_data", None)
        if image_data is None or not GROUNDING_DINO_AVAILABLE:
            return []
        raw = vision_mod.detect_grounding_dino(
            image_data if isinstance(image_data, bytes) else bytes(image_data),
            object_queries=self._object_queries,
            model_id=self._model_id,
            device=self._device,
            detection_threshold=self._detection_threshold,
            text_threshold=self._text_threshold,
            box_score_min=self._box_score_min,
        )
        signals = []
        for det in raw:
            conf = float(det["confidence"])
            x0, y0, w, h = det["bbox"]
            payload = {
                "type": "vision_object",
                "label": det["label"],
                "confidence": conf,
                "bbox": [x0, y0, w, h],
                "source": "image",
                "model": "grounding_dino",
            }
            bounding_box = {"x": x0, "y": y0, "width": w, "height": h}
            signals.append(
                Signal(
                    signal_id=str(uuid.uuid4()),
                    signal_type=SignalType.OBJECT,
                    source_model=self.model_name,
                    confidence=conf,
                    raw_data=payload,
                    bounding_box=bounding_box,
                    detected_at=datetime.now(),
                )
            )
        return signals
