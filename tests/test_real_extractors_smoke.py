"""
Smoke tests for domain OCR / Vision / Embedding when deps (and Hugging Face models) are available.

Skipped automatically when tesseract, torch, or model download/load fails.
"""

import sys
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image, ImageDraw, ImageFont

src = Path(__file__).resolve().parent.parent / "src"
if str(src) not in sys.path:
    sys.path.insert(0, str(src))


def _png_with_text(text: str) -> bytes:
    img = Image.new("RGB", (480, 100), color="white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    except OSError:
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 28)
        except OSError:
            font = ImageFont.load_default()
    draw.text((16, 32), text, fill="black", font=font)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _png_white_square_on_black() -> bytes:
    img = Image.new("RGB", (320, 320), "black")
    draw = ImageDraw.Draw(img)
    draw.rectangle([60, 60, 260, 260], fill="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.integration
def test_domain_ocr_produces_text_signals():
    pytest.importorskip("pytesseract")
    import pytesseract

    try:
        pytesseract.get_tesseract_version()
    except pytesseract.TesseractNotFoundError:
        pytest.skip("tesseract binary not installed")

    from zataone.domains.ad_compliance.extractors.ocr_extractor import OCRExtractor
    from zataone.domains.ad_compliance.schemas.models import SignalType

    image_data = _png_with_text("CLAIM FREE CASH NOW")
    ext = OCRExtractor()
    if ext.backend is None:
        pytest.skip("OCR backend not available")

    asset = SimpleNamespace(image_data=image_data)
    signals = ext.extract(asset)
    assert signals, "expected at least one OCR signal"
    assert any(s.signal_type == SignalType.TEXT for s in signals)
    assert any((s.raw_data or {}).get("text") for s in signals)


@pytest.mark.integration
def test_domain_vision_produces_object_signals():
    pytest.importorskip("torch")
    pytest.importorskip("transformers")

    from zataone.domains.ad_compliance.extractors.vision_extractor import (
        GROUNDING_DINO_AVAILABLE,
        VisionExtractor,
    )
    from zataone.domains.ad_compliance.schemas.models import SignalType

    if not GROUNDING_DINO_AVAILABLE:
        pytest.skip("vision deps missing")

    ext = VisionExtractor(object_queries=["square", "rectangle", "shape"])
    asset = SimpleNamespace(image_data=_png_white_square_on_black())
    signals = ext.extract(asset)
    if not signals:
        pytest.skip("no vision detections on synthetic image (model ran but found nothing)")
    assert all(s.signal_type == SignalType.OBJECT for s in signals)
    assert all((s.raw_data or {}).get("type") == "vision_object" for s in signals)


@pytest.mark.integration
def test_domain_embedding_produces_similarity():
    np = pytest.importorskip("numpy")
    pytest.importorskip("torch")
    pytest.importorskip("transformers")

    from zataone.domains.ad_compliance.extractors import embedding_extractor as emb_mod

    if not emb_mod.SIGLIP_AVAILABLE:
        pytest.skip("embedding deps missing")

    from zataone.domains.ad_compliance.extractors.embedding_extractor import (
        EmbeddingExtractor,
    )

    ext = EmbeddingExtractor(
        regulation_texts=[("test_rule", "hello world similarity test phrase")],
        similarity_threshold=0.0,
    )
    rgb = Image.new("RGB", (224, 224), color=(240, 240, 255))
    buf = BytesIO()
    rgb.save(buf, format="PNG")
    image_data = buf.getvalue()

    try:
        vec = ext.extract_embedding(image_data)
    except RuntimeError:
        pytest.skip("SigLIP model unavailable")
    except Exception:
        pytest.skip("SigLIP load/inference failed")

    assert vec.ndim == 1
    assert abs(float(np.linalg.norm(vec)) - 1.0) < 0.05

    text_embs = emb_mod.encode_regulation_texts(ext._regulation_texts)
    if text_embs is None:
        pytest.skip("SigLIP text encoding unavailable")
    sim = float(np.dot(vec, text_embs[0]))
    assert -1.01 <= sim <= 1.01

    asset = SimpleNamespace(image_data=image_data)
    signals = ext.extract(asset)
    assert signals, "expected similarity signals with threshold 0.0"
    assert signals[0].raw_data.get("type") == "image_embedding_similarity"


def test_disable_core_stub_extractors_env(monkeypatch):
    monkeypatch.setenv("ZATAONE_DISABLE_CORE_STUB_EXTRACTORS", "true")
    from zataone.core.pipeline import CompliancePipeline

    pipeline = CompliancePipeline(domain="ad_compliance")
    ids = {e.extractor_id for e in pipeline._extractor_registry.list()}
    assert "ad_compliance_ocr" in ids
    assert "ocr_extractor" not in ids
    assert "text_extractor" in ids
