"""
Domain-agnostic audio → transcript (faster-whisper). No policy or domain terms.
"""

from __future__ import annotations

import logging
import os
import tempfile
from typing import Any, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    from faster_whisper import WhisperModel

    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False
    WhisperModel = None  # type: ignore

_model: Any = None
_model_key: Optional[str] = None


def _get_model():
    global _model, _model_key
    if not FASTER_WHISPER_AVAILABLE:
        return None
    model_size = os.environ.get("WHISPER_MODEL", "base")
    device = os.environ.get("WHISPER_DEVICE", "cpu")
    compute_type = os.environ.get("WHISPER_COMPUTE_TYPE", "int8")
    key = f"{model_size}|{device}|{compute_type}"
    if _model is None or _model_key != key:
        try:
            _model = WhisperModel(model_size, device=device, compute_type=compute_type)
            _model_key = key
        except Exception:
            logger.exception("modality.asr: failed to load Whisper model %s", model_size)
            _model = None
            _model_key = None
    return _model


def _suffix_for_filename(name: str) -> str:
    n = (name or "").lower()
    for ext in (".wav", ".mp3", ".webm", ".ogg", ".m4a", ".flac", ".mp4", ".mpeg"):
        if n.endswith(ext):
            return ext
    return ".wav"


def transcribe_audio_bytes(
    audio_data: bytes,
    filename: str = "audio.wav",
) -> Tuple[str, Any]:
    """
    Transcribe raw audio bytes. Returns (text, info) where info is faster-whisper info object.

    Raises RuntimeError if faster-whisper unavailable or transcription fails.
    """
    if not FASTER_WHISPER_AVAILABLE:
        raise RuntimeError("faster-whisper not installed")
    model = _get_model()
    if model is None:
        raise RuntimeError("Whisper model not loaded")

    suffix = _suffix_for_filename(filename)
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_data if isinstance(audio_data, bytes) else bytes(audio_data))
        path = tmp.name
    try:
        segments, info = model.transcribe(
            path,
            beam_size=int(os.environ.get("WHISPER_BEAM_SIZE", "5")),
            language=os.environ.get("WHISPER_LANGUAGE") or None,
        )
        parts: list[str] = []
        for seg in segments:
            t = (seg.text or "").strip()
            if t:
                parts.append(t)
        text = " ".join(parts).strip()
        return text, info
    finally:
        try:
            import os as _os

            _os.unlink(path)
        except OSError:
            pass
