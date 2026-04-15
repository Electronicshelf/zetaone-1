# zataone explainability graph builder

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from zataone.models import Signal, Verdict, Violation


def _signal_to_dict(signal: Signal) -> dict[str, Any]:
    """Convert Signal model to JSON-serializable dict for explainability."""
    return {
        "id": str(signal.id),
        "signal_type": signal.signal_type,
        "extractor_id": signal.extractor_id,
        "value": signal.value,
        "confidence": signal.confidence,
    }


def build_explainability_graph(asset_id: uuid.UUID, session: Session) -> dict[str, Any]:
    """
    Build structured explainability graph for an asset.

    Returns:
        {
            verdict: {...},
            violations: [
                {
                    violation_type: str,
                    rule_id: str,
                    signals: [...]
                }
            ]
        }
    """
    verdict = (
        session.query(Verdict)
        .filter(Verdict.asset_id == asset_id)
        .order_by(Verdict.created_at.desc())
        .first()
    )
    verdict_data = dict(verdict.result) if verdict and verdict.result else {}

    violations_q = session.query(Violation).filter(Violation.asset_id == asset_id).all()

    # Group violations by (violation_type, rule_id), collect unique signals per group
    groups: dict[tuple[str, str], set[uuid.UUID]] = {}
    for v in violations_q:
        key = (v.violation_type, v.rule_id)
        groups.setdefault(key, set()).add(v.signal_id)

    violations_out = []
    for (violation_type, rule_id), signal_ids in groups.items():
        signals = []
        for sid in signal_ids:
            sig = session.query(Signal).filter(Signal.id == sid).first()
            if sig:
                signals.append(_signal_to_dict(sig))
        violations_out.append(
            {
                "violation_type": violation_type,
                "rule_id": rule_id,
                "signals": signals,
            }
        )

    return {
        "verdict": verdict_data,
        "violations": violations_out,
    }
