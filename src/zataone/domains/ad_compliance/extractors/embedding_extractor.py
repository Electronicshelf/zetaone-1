"""
SigLIP embedding extractor — thin domain wrapper over zataone.extractors.modality.embedding.
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime
from typing import Any, List, Optional, Tuple

import numpy as np

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

from zataone.extractors.modality import embedding as emb_mod

SIGLIP_AVAILABLE = emb_mod.SIGLIP_AVAILABLE


def encode_regulation_texts(
    regulation_texts: List[Tuple[str, str]],
    model_name: str | None = None,
) -> Optional[List[np.ndarray]]:
    """Re-export for tests; default model matches domain YAML."""
    mn = model_name or "google/siglip-base-patch16-224"
    return emb_mod.encode_regulation_texts(regulation_texts, model_name=mn)


class EmbeddingExtractor(BaseExtractor):
    """SigLIP similarity: modality scores → domain signals."""

    extractor_id = "ad_compliance_embedding"
    version = "1.0.0"

    def __init__(
        self,
        regulation_texts: List[Tuple[str, str]] | None = None,
        similarity_threshold: float = 0.6,
        model_name: str | None = None,
    ):
        self.model_name = "siglip"
        self._regulation_texts = regulation_texts or [
            ("misleading_claims", "misleading or exaggerated advertising claims"),
            ("medical_health_claims", "unsubstantiated or guaranteed medical or health claims"),
            ("fraud_scams_deceptive", "fraud scams and deceptive practices financial urgency impersonation"),
            ("weapons_ammunition_explosives", "weapons ammunition explosives restricted goods"),
            ("tobacco_nicotine", "tobacco nicotine products vaping restricted"),
            ("gambling", "gambling betting casino restricted"),
            ("financial_products_and_guarantees", "financial products guarantees loans investment insurance"),
            ("cryptocurrency_services", "cryptocurrency crypto bitcoin trading exchange financial"),
        ]
        self._similarity_threshold = similarity_threshold
        self._model_name = model_name or "google/siglip-base-patch16-224"

    def extract_embedding(self, image_data: bytes) -> np.ndarray:
        """Public for tests."""
        return emb_mod.encode_image_bytes(image_data, model_name=self._model_name)

    def extract(self, asset: Any) -> List[Signal]:
        image_data = getattr(asset, "image_data", None)
        if image_data is None or not self._regulation_texts or not SIGLIP_AVAILABLE:
            return []
        scores = emb_mod.similarity_scores(
            image_data if isinstance(image_data, bytes) else bytes(image_data),
            self._regulation_texts,
            model_name=self._model_name,
        )
        if not scores:
            return []
        signals = []
        for name, score in scores:
            if score <= self._similarity_threshold:
                continue
            raw = {
                "type": "image_embedding_similarity",
                "regulation": name,
                "score": score,
                "model": self.model_name,
            }
            signals.append(
                Signal(
                    signal_id=str(uuid.uuid4()),
                    signal_type=SignalType.SCENE,
                    source_model=self.model_name,
                    confidence=score,
                    raw_data=raw,
                    bounding_box=None,
                    detected_at=datetime.now(),
                )
            )
        return signals
