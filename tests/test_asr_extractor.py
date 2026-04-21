"""ASR extractor unit tests (skip if faster-whisper not installed)."""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

src = Path(__file__).resolve().parent.parent / "src"
if str(src) not in sys.path:
    sys.path.insert(0, str(src))

import importlib.util

import pytest

_HAS_FW = importlib.util.find_spec("faster_whisper") is not None


@pytest.mark.skipif(not _HAS_FW, reason="faster-whisper not installed")
def test_asr_extractor_returns_empty_without_audio_type():
    from zataone.domains.ad_compliance.extractors.asr_extractor import AsrExtractor

    ext = AsrExtractor()
    assert ext.extract(SimpleNamespace(type="text", content="hi")) == []


def test_asr_extractor_skips_when_no_faster_whisper(monkeypatch):
    import zataone.extractors.modality.asr as asr_mod
    from zataone.domains.ad_compliance.extractors.asr_extractor import AsrExtractor

    monkeypatch.setattr(asr_mod, "FASTER_WHISPER_AVAILABLE", False)
    ext = AsrExtractor()
    out = ext.extract(
        SimpleNamespace(type="audio", audio_data=b"fake", audio_filename="x.wav")
    )
    assert out == []
