"""
Unit tests for Evidence graph - Evidence links Signal and Violation.
Requires PostgreSQL at DATABASE_URL. Run with: pytest tests/test_evidence_graph.py -v
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

from zataone.models import Asset, Evidence, Signal, Tenant, Violation
from zataone.services.evidence_service import EvidenceService
from zataone.services.signal_service import SignalService
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
        evidence_data={"matched_term": "guaranteed", "confidence": 0.9, "rule_name": "Test Rule"},
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


def test_evidence_rows_created_with_correct_linkage(db_session):
    """Verify Evidence rows created with correct signal_id, violation_id, rule_id."""
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
    evidence_records = evidence_service.persist_evidence(
        db_session, asset.id, signal_records, violation_records
    )

    db_session.commit()

    assert len(evidence_records) == 1
    ev = evidence_records[0]
    assert ev.asset_id == asset.id
    assert ev.signal_id == sig1_id
    assert ev.violation_id == violation_records[0].id
    assert ev.rule_id == "rule_1"
    assert ev.evidence_data.get("matched_term") == "guaranteed"

    rows = db_session.query(Evidence).filter(Evidence.asset_id == asset.id).all()
    assert len(rows) == 1
    assert rows[0].signal_id == sig1_id
    assert rows[0].violation_id == violation_records[0].id
    assert rows[0].rule_id == "rule_1"


def test_evidence_multiple_violations_correct_linkage(db_session):
    """Verify multiple Evidence rows with correct signal_id and violation_id."""
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
        _make_violation(str(sig_b), "rule_2"),
        _make_violation(str(sig_a), "rule_2"),
    ]
    violation_service = ViolationService()
    violation_records = violation_service.persist_violations(
        db_session, asset.id, signal_records, violations
    )

    evidence_service = EvidenceService()
    evidence_records = evidence_service.persist_evidence(
        db_session, asset.id, signal_records, violation_records
    )

    db_session.commit()

    assert len(evidence_records) == 3

    for ev, v_rec in zip(evidence_records, violation_records):
        assert ev.signal_id == v_rec.signal_id
        assert ev.violation_id == v_rec.id
        assert ev.rule_id == v_rec.rule_id

    violation_ids = {ev.violation_id for ev in evidence_records}
    assert len(violation_ids) == 3
