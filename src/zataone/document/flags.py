# zataone document-centric feature flags

from __future__ import annotations

import os


def document_centric_enabled() -> bool:
    """
    When True, PolicyEngine matches rules against unified document text.
    Default False preserves per-token / per-signal fragment matching.
    """
    v = os.environ.get("ZATAONE_DOCUMENT_CENTRIC", "").strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    if v in ("0", "false", "no", "off"):
        return False
    return False
