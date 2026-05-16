# zataone policy match span helpers

from __future__ import annotations

import re
from typing import Any


def locate_match_span(
    document_text: str,
    matched_term: str,
    rule: dict[str, Any],
) -> dict[str, int | str] | None:
    """
    Find character span of matched_term in document_text.
    Prefers regex pattern spans from rule when matched_term came from a pattern.
    """
    if not document_text or not matched_term:
        return None

    for pattern_info in rule.get("patterns", []):
        pattern = pattern_info.get("pattern", "")
        if not pattern:
            continue
        match = re.search(pattern, document_text, re.IGNORECASE)
        if match and match.group(0).lower() == matched_term.lower():
            return {"start": match.start(), "end": match.end(), "text": match.group(0)}

    idx = document_text.lower().find(matched_term.lower())
    if idx >= 0:
        return {
            "start": idx,
            "end": idx + len(matched_term),
            "text": document_text[idx : idx + len(matched_term)],
        }
    return None


def pick_signal_id_for_span(
    span: dict[str, int | str] | None,
    document_spans: list[Any],
    text_signals: list[Any],
    source_signal_ids: list[str],
) -> str:
    """Choose originating signal_id for explainability linkage."""
    if span and document_spans:
        start = int(span["start"])
        end = int(span["end"])
        for dsp in document_spans:
            ds = getattr(dsp, "start", None)
            de = getattr(dsp, "end", None)
            if ds is None and isinstance(dsp, dict):
                ds, de = dsp.get("start"), dsp.get("end")
            if ds is not None and de is not None and ds <= start and de >= end:
                sid = getattr(dsp, "source_signal_id", None) or (
                    dsp.get("source_signal_id") if isinstance(dsp, dict) else None
                )
                if sid:
                    return str(sid)
            if ds is not None and de is not None and not (de <= start or ds >= end):
                sid = getattr(dsp, "source_signal_id", None) or (
                    dsp.get("source_signal_id") if isinstance(dsp, dict) else None
                )
                if sid:
                    return str(sid)

    for signal in text_signals:
        sid = getattr(signal, "signal_id", None)
        if sid:
            return str(sid)

    if source_signal_ids:
        return source_signal_ids[0]
    return "document"
