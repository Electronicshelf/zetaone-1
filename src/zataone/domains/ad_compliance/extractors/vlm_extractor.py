"""
VLM extractor — thin domain wrapper; API call lives in modality.vlm.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List

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


from zataone.extractors.modality import vlm as vlm_mod

# Re-export for policy / borderline routing (same import path as before)
analyze_image_context = vlm_mod.analyze_image_context


class VLMExtractor(BaseExtractor):
    """VLM: borderline context via OpenAI vision API; extract() is empty by design."""

    extractor_id = "ad_compliance_vlm"
    version = "1.0.0"

    def __init__(
        self,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        env_api_key: str | None = None,
    ):
        self.model_name = "gpt_4o_vision_api"
        self._model = model or "gpt-4o"
        self._max_tokens = 120 if max_tokens is None else int(max_tokens)
        self._temperature = 0.2 if temperature is None else float(temperature)
        self._env_api_key = env_api_key or "VLM_API_KEY"

    def extract(self, asset: Any) -> List:
        """Base extract returns empty — VLM is used for borderline context only."""
        return []

    def analyze_image_context(
        self,
        image_bytes: bytes,
        ocr_texts: List[str],
        vision_objects: List[Dict[str, Any]],
        policy_id: str,
    ) -> str:
        return vlm_mod.analyze_image_context(
            image_bytes,
            ocr_texts,
            vision_objects,
            policy_id,
            model=self._model,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
            api_key_env=self._env_api_key,
        )
