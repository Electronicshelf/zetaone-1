"""
Whisper-based ASR for audio assets — thin domain wrapper over modality.asr.
"""

from __future__ import annotations

import logging
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

from zataone.extractors.modality import asr as asr_mod

logger = logging.getLogger(__name__)


class AsrExtractor(BaseExtractor):
    """ASR: modality transcription → domain signal for policy engine."""

    extractor_id = "ad_compliance_asr"
    version = "1.0.0"

    def __init__(self) -> None:
        self.model_name = "faster_whisper"

    def extract(self, asset: Any) -> List[Signal]:
        asset_type = getattr(asset, "type", None)
        if asset_type != "audio":
            return []
        audio_data = getattr(asset, "audio_data", None)
        if not audio_data:
            return []
        if not asr_mod.FASTER_WHISPER_AVAILABLE:
            logger.warning("ASR: faster-whisper not installed; skip audio transcription")
            return []

        filename = getattr(asset, "audio_filename", None) or "audio.wav"
        try:
            text, info = asr_mod.transcribe_audio_bytes(
                audio_data if isinstance(audio_data, bytes) else bytes(audio_data),
                str(filename),
            )
        except Exception:
            logger.exception("ASR: transcription failed")
            return []

        if not text:
            return []

        conf = min(1.0, max(0.0, float(getattr(info, "language_probability", 1.0) or 1.0)))
        payload = {
            "type": "asr_text",
            "text": text,
            "source": "audio",
            "model": self.model_name,
            "language": getattr(info, "language", None),
        }
        return [
            Signal(
                signal_id=str(uuid.uuid4()),
                signal_type=SignalType.TEXT,
                source_model=self.model_name,
                confidence=conf,
                raw_data=payload,
                bounding_box=None,
                detected_at=datetime.now(),
            )
        ]
