"""
Unit tests for ViolationService.
Requires PostgreSQL at DATABASE_URL. Run with: pytest tests/test_violation_service.py -v
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

from zataone.models import Asset, Signal, Tenant, Violation
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


def _make_violation(rule_id: str, evidence_signal_ids: list[str]) -> dict:
    evidence = [
        {"signal_id": sid, "evidence_type": "text_match", "data": {"matched_term": "guaranteed"}}
        for sid in evidence_signal_ids
    ]
    return {
        "rule_id": rule_id,
        "rule_name": "Test Rule",
        "severity": "HIGH",
        "evidence": evidence,
    }


@pytest.fixture
def db_session():
    """Create tables and yield a session. Skip if DB unavailable."""
    try:
        create_all_tables()
    except Exception as e:
        pytest.skip(f"Database not available: {e}")

    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def test_persist_violations_creates_rows_and_links_signals(db_session):
    """Create fake signals and violations, persist them, verify violation rows and signal_id linkage."""
    # Create tenant and asset
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

    # Create signals via SignalService (to get proper signal_records)
    sig1_id = uuid.uuid4()
    sig2_id = uuid.uuid4()
    signals = [_make_signal(str(sig1_id)), _make_signal(str(sig2_id))]

    signal_service = SignalService()
    signal_records = signal_service.persist_signals(db_session, asset.id, signals)

    assert len(signal_records) == 2
    assert signal_records[0].id == sig1_id
    assert signal_records[1].id == sig2_id

    # Create violations: one links to sig1, one links to both sig1 and sig2
    violations = [
        _make_violation("rule_1", [str(sig1_id)]),
        _make_violation("rule_2", [str(sig1_id), str(sig2_id)]),
    ]

    violation_service = ViolationService()
    persisted = violation_service.persist_violations(
        db_session, asset.id, signal_records, violations
    )

    db_session.commit()

    # Verify violation rows exist
    assert len(persisted) == 3  # 1 + 2 evidence items
    rows = db_session.query(Violation).filter(Violation.asset_id == asset.id).all()
    assert len(rows) == 3

    # Verify correct signal_id linkage
    by_rule = {}
    for r in rows:
        by_rule.setdefault(r.rule_id, []).append(r)

    assert len(by_rule["rule_1"]) == 1
    assert by_rule["rule_1"][0].signal_id == sig1_id

    assert len(by_rule["rule_2"]) == 2
    signal_ids_rule2 = {r.signal_id for r in by_rule["rule_2"]}
    assert signal_ids_rule2 == {sig1_id, sig2_id}

    # Verify fields
    for r in rows:
        assert r.asset_id == asset.id
        assert r.rule_id in ("rule_1", "rule_2")
        assert r.violation_type == "text_match"
        assert r.severity == 0.7  # HIGH
        assert r.created_at is not None
