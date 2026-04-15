"""
Unit tests for PolicyEngine.evaluate() violation output.
Verifies violations returned, signal_id mapped, rule_id populated.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

# Ensure src is first for correct zataone import
src = Path(__file__).resolve().parent.parent / "src"
if str(src) not in sys.path:
    sys.path.insert(0, str(src))

import pytest

from zataone.policy_engine.engine import PolicyEngine
from zataone.schemas.violation import Violation


def _make_signal(signal_id: str, text: str) -> SimpleNamespace:
    return SimpleNamespace(
        signal_id=signal_id,
        signal_type="keyword",
        source_model="text_extractor",
        confidence=0.9,
        raw_data={"text": text, "type": "ocr_text"},
    )


def test_evaluate_returns_violations_with_signal_id_and_rule_id():
    """Verify evaluate() returns Violation objects with signal_id and rule_id populated."""
    engine = PolicyEngine()
    engine.load_policy_pack(
        rules={
            "misleading_exaggerated_claims": {
                "name": "Misleading Claims",
                "prohibited_terms": ["guaranteed", "100%", "instant"],
                "severity": "HIGH",
            },
        }
    )

    sig1_id = "sig-001"
    signals = [_make_signal(sig1_id, "This product is guaranteed to work")]

    violations = engine.evaluate(signals)

    assert len(violations) >= 1
    for v in violations:
        assert isinstance(v, Violation)
        assert v.signal_id == sig1_id
        assert v.rule_id == "misleading_exaggerated_claims"
        assert v.violation_type == "text_match"
        assert isinstance(v.severity, float)
        assert v.severity >= 0.0 and v.severity <= 1.0
        assert isinstance(v.evidence_data, dict)
        assert "matched_term" in v.evidence_data or "rule_name" in v.evidence_data


def test_evaluate_no_violations_when_clean():
    """Verify no violations when content does not match rules."""
    engine = PolicyEngine()
    engine.load_policy_pack(
        rules={
            "misleading_exaggerated_claims": {
                "name": "Misleading Claims",
                "prohibited_terms": ["guaranteed"],
                "severity": "HIGH",
            },
        }
    )

    signals = [_make_signal("sig-002", "This product works well")]

    violations = engine.evaluate(signals)

    assert len(violations) == 0


def test_evaluate_multiple_signals_maps_signal_id_correctly():
    """Verify each violation references the correct originating signal."""
    engine = PolicyEngine()
    engine.load_policy_pack(
        rules={
            "test_rule": {
                "name": "Test",
                "prohibited_terms": ["bad"],
                "severity": "MEDIUM",
            },
        }
    )

    sig_a = _make_signal("sig-a", "This is bad")
    sig_b = _make_signal("sig-b", "Also bad")
    signals = [sig_a, sig_b]

    violations = engine.evaluate(signals)

    assert len(violations) >= 2
    signal_ids = {v.signal_id for v in violations}
    assert "sig-a" in signal_ids
    assert "sig-b" in signal_ids
    for v in violations:
        assert v.rule_id == "test_rule"
