"""
Unit tests for explainability graph builder.
Requires PostgreSQL at DATABASE_URL. Run with: pytest tests/test_graph_builder.py -v
"""

import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

# Ensure src is first for correct zataone import
src = Path(__file__).resolve().parent.parent / "src"
if str(src) not in sys.path:
    sys.path.insert(0, str(src))

import pytest

from zataone.explainability.graph_builder import build_explainability_graph
from zataone.models import Asset, Evidence, Signal, Tenant, Verdict, Violation
from zataone.services.evidence_service import EvidenceService
from zataone.services.signal_service import SignalService
from zataone.services.verdict_service import VerdictService
from zataone.services.violation_service import ViolationService
from zataone.storage.database import create_all_tables, get_session_factory


def _make_signal(signal_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        signal_id=signal_id,
        signal_type="keyword",
        source_model="test_extractor",
        raw_data={"value": "guaranteed"},
        confidence=0.9,
    )


def _make_violation(signal_id: str, rule_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        signal_id=signal_id,
        rule_id=rule_id,
        violation_type="text_match",
        severity=0.7,
        evidence_data={"matched_term": "guaranteed", "rule_name": "Test Rule"},
    )


@pytest.fixture
def db_session():
    """Create tables and yield a session. Skip if DB unavailable."""
    from sqlalchemy import text

    from zataone.storage.database import get_engine

    try:
        create_all_tables()
        engine = get_engine()
        with engine.connect() as conn:
            for sql in [
                "ALTER TABLE assets ADD COLUMN IF NOT EXISTS status VARCHAR(32) DEFAULT 'processing'",
                "ALTER TABLE assets ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(255)",
                "ALTER TABLE violations ADD COLUMN IF NOT EXISTS evidence_data JSONB DEFAULT '{}'",
                "ALTER TABLE evidence ADD COLUMN IF NOT EXISTS violation_id UUID REFERENCES violations(id)",
                "ALTER TABLE evidence ADD COLUMN IF NOT EXISTS evidence_data JSONB DEFAULT '{}'",
            ]:
                try:
                    conn.execute(text(sql))
                    conn.commit()
                except Exception:
                    pass
    except Exception as e:
        pytest.skip(f"Database not available: {e}")

    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def test_build_explainability_graph_returns_verdict_and_violations(db_session):
    """build_explainability_graph returns verdict and violations with signals."""
    tenant = Tenant(name="default")
    db_session.add(tenant)
    db_session.flush()

    asset = Asset(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        content_hash="abc123",
        type="text",
        status="completed",
    )
    db_session.add(asset)
    db_session.flush()

    sig1_id = uuid.uuid4()
    signals = [_make_signal(str(sig1_id))]
    signal_service = SignalService()
    signal_records = signal_service.persist_signals(db_session, asset.id, signals)

    violations = [_make_violation(str(sig1_id), "rule_1")]
    violation_service = ViolationService()
    violation_records = violation_service.persist_violations(
        db_session, asset.id, signal_records, violations
    )

    evidence_service = EvidenceService()
    evidence_service.persist_evidence(
        db_session, asset.id, signal_records, violation_records
    )

    verdict_service = VerdictService()
    verdict_service.persist_verdict(
        db_session,
        asset.id,
        {
            "verdict": "likely_rejected",
            "risk_score": 0.8,
            "status": "NON_COMPLIANT",
            "violations": [{"rule_id": "rule_1"}],
            "signals": [],
        },
    )

    db_session.commit()

    graph = build_explainability_graph(asset.id, db_session)

    assert "verdict" in graph
    assert "violations" in graph

    assert graph["verdict"]["verdict"] == "likely_rejected"
    assert graph["verdict"]["risk_score"] == 0.8
    assert graph["verdict"]["status"] == "NON_COMPLIANT"

    assert len(graph["violations"]) == 1
    v = graph["violations"][0]
    assert v["violation_type"] == "text_match"
    assert v["rule_id"] == "rule_1"
    assert "signals" in v
    assert len(v["signals"]) == 1
    sig = v["signals"][0]
    assert sig["id"] == str(sig1_id)
    assert sig["signal_type"] == "keyword"
    assert sig["extractor_id"] == "test_extractor"
    assert sig["confidence"] == 0.9


def test_build_explainability_graph_groups_violations_by_rule(db_session):
    """Violations with same rule_id but different signals are grouped with all signals."""
    tenant = Tenant(name="default")
    db_session.add(tenant)
    db_session.flush()

    asset = Asset(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        content_hash="def456",
        type="text",
        status="completed",
    )
    db_session.add(asset)
    db_session.flush()

    sig_a = uuid.uuid4()
    sig_b = uuid.uuid4()
    signals = [_make_signal(str(sig_a)), _make_signal(str(sig_b))]
    signal_service = SignalService()
    signal_records = signal_service.persist_signals(db_session, asset.id, signals)

    violations = [
        _make_violation(str(sig_a), "rule_1"),
        _make_violation(str(sig_b), "rule_1"),
    ]
    violation_service = ViolationService()
    violation_records = violation_service.persist_violations(
        db_session, asset.id, signal_records, violations
    )

    evidence_service = EvidenceService()
    evidence_service.persist_evidence(
        db_session, asset.id, signal_records, violation_records
    )

    verdict_service = VerdictService()
    verdict_service.persist_verdict(
        db_session,
        asset.id,
        {"verdict": "likely_rejected", "risk_score": 0.9, "status": "NON_COMPLIANT"},
    )

    db_session.commit()

    graph = build_explainability_graph(asset.id, db_session)

    assert len(graph["violations"]) == 1
    v = graph["violations"][0]
    assert v["rule_id"] == "rule_1"
    assert len(v["signals"]) == 2
    signal_ids = {s["id"] for s in v["signals"]}
    assert signal_ids == {str(sig_a), str(sig_b)}


def test_build_explainability_graph_empty_verdict_when_none(db_session):
    """Returns empty verdict when no verdict exists for asset."""
    tenant = Tenant(name="default")
    db_session.add(tenant)
    db_session.flush()

    asset = Asset(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        content_hash="ghi789",
        type="text",
        status="processing",
    )
    db_session.add(asset)
    db_session.flush()
    db_session.commit()

    graph = build_explainability_graph(asset.id, db_session)

    assert graph["verdict"] == {}
    assert graph["violations"] == []
