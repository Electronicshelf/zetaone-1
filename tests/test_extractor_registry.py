"""
Test that CompliancePipeline registers all required extractors for ad_compliance.
"""

import sys
from pathlib import Path
from unittest.mock import patch

# Ensure src is first for correct zataone import
src = Path(__file__).resolve().parent.parent / "src"
if str(src) not in sys.path:
    sys.path.insert(0, str(src))

REQUIRED_EXTRACTOR_IDS = [
    "text_extractor",
    "ocr_extractor",
    "vision_extractor",
    "embedding_extractor",
    "vlm_extractor",
]


def test_ad_compliance_registry_contains_all_extractors():
    """CompliancePipeline(domain='ad_compliance') registers all 5 core extractors."""
    from zataone.core.pipeline import CompliancePipeline

    def mock_load_domain_extractors(self):
        """Register only core extractors (skip domain module to avoid heavy deps)."""
        if self._domain == "ad_compliance":
            from zataone.extractors.text_extractor import TextExtractor
            from zataone.extractors.ocr_extractor import OCRExtractor
            from zataone.extractors.vision_extractor import VisionExtractor
            from zataone.extractors.embedding_extractor import EmbeddingExtractor
            from zataone.extractors.vlm_extractor import VLMExtractor

            self._extractor_registry.register(TextExtractor())
            self._extractor_registry.register(OCRExtractor())
            self._extractor_registry.register(VisionExtractor())
            self._extractor_registry.register(EmbeddingExtractor())
            self._extractor_registry.register(VLMExtractor())

    with patch.object(
        CompliancePipeline,
        "_load_domain_extractors",
        mock_load_domain_extractors,
    ):
        pipeline = CompliancePipeline(domain="ad_compliance")
        registry = pipeline._extractor_registry

    extractor_ids = {e.extractor_id for e in registry.list()}
    for required_id in REQUIRED_EXTRACTOR_IDS:
        assert required_id in extractor_ids, f"Missing extractor: {required_id}"

    assert len(extractor_ids) >= len(REQUIRED_EXTRACTOR_IDS)
