"""
Integration test: full compliance graph persistence.
Verifies asset, signals, violations, evidence, verdict all linked correctly.
Requires PostgreSQL at DATABASE_URL. Run with: pytest tests/test_compliance_graph_full.py -v
"""

import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# Ensure src is first for correct zataone import
src = Path(__file__).resolve().parent.parent / "src"
if str(src) not in sys.path:
    sys.path.insert(0, str(src))

import pytest

from zataone.core.pipeline import CompliancePipeline
from zataone.extractors.registry import ExtractorRegistry
from zataone.models import Asset, Evidence, Signal, Verdict, Violation
from zataone.storage.database import create_all_tables, get_session_factory


def _make_mock_signal(signal_id: str, extractor_id: str = "ad_compliance_mock") -> SimpleNamespace:
    """Create a mock signal with signal_id for violation linkage."""
    return SimpleNamespace(
        signal_id=signal_id,
        signal_type="keyword",
        source_model=extractor_id,
        raw_data={"text": "guaranteed instant cure", "value": "guaranteed"},
        confidence=0.9,
    )


def _mock_load_extractors(self):
    """Replace domain extractors with mocks that return signals with signal_id."""
    sig_id = str(uuid.uuid4())
    ext = MagicMock()
    ext.extractor_id = "ad_compliance_mock"
    ext.version = "1.0"
    ext.extract.return_value = [_make_mock_signal(sig_id)]
    self._extractor_registry = ExtractorRegistry()
    self._extractor_registry.register(ext)


@pytest.fixture(scope="module")
def db_setup():
    """Ensure DB is available, tables exist, migrations applied."""
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


@patch("zataone.core.pipeline.CompliancePipeline._load_domain_extractors", _mock_load_extractors)
def test_compliance_graph_full_persistence(db_setup):
    """Run pipeline and verify DB contains asset, signals, violations, evidence, verdict linked correctly."""
    pipeline = CompliancePipeline(domain="ad_compliance")
    asset = SimpleNamespace(
        asset_id=None,
        content="Guaranteed instant cure",
        type="text",
        metadata={},
    )

    result = pipeline.run(asset, persist=True)

    assert "verdict" in result
    assert "violations" in result

    session = get_session_factory()()
    try:
        assets = session.query(Asset).order_by(Asset.created_at.desc()).limit(1).all()
        assert len(assets) >= 1, "Expected at least one asset"
        asset_record = assets[0]

        signals = session.query(Signal).filter(Signal.asset_id == asset_record.id).all()
        assert len(signals) >= 1, "Expected at least one signal"

        violations = session.query(Violation).filter(Violation.asset_id == asset_record.id).all()
        assert len(violations) >= 1, "Expected at least one violation"

        evidence = session.query(Evidence).filter(Evidence.asset_id == asset_record.id).all()
        assert len(evidence) >= 1, "Expected at least one evidence"

        verdict = (
            session.query(Verdict)
            .filter(Verdict.asset_id == asset_record.id)
            .order_by(Verdict.created_at.desc())
            .first()
        )
        assert verdict is not None, "Expected verdict"

        for ev in evidence:
            assert ev.signal_id is not None
            assert ev.violation_id is not None
            assert ev.rule_id
            assert ev.asset_id == asset_record.id
            signal_ids = {s.id for s in signals}
            violation_ids = {v.id for v in violations}
            assert ev.signal_id in signal_ids, f"Evidence.signal_id {ev.signal_id} not in signals"
            assert ev.violation_id in violation_ids, f"Evidence.violation_id {ev.violation_id} not in violations"

        for v in violations:
            assert v.signal_id in {s.id for s in signals}
            assert v.asset_id == asset_record.id
    finally:
        session.close()
