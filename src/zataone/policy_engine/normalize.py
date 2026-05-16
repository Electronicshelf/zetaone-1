# zataone policy text normalization

from __future__ import annotations

import re
import unicodedata


def normalize_for_matching(text: str) -> str:
    """
    Deterministic normalization before policy DSL evaluation.
    NFC unicode, lowercase, whitespace cleanup.
    """
    if not text:
        return ""
    t = unicodedata.normalize("NFC", text)
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = t.lower()
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()
