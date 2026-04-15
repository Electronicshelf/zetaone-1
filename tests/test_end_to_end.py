"""
End-to-end tests: upload text/image assets via API, verify signals, verdict, persistence.
Requires PostgreSQL at DATABASE_URL. Run with: pytest tests/test_end_to_end.py -v -s
"""

import base64
import sys
import time
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# Ensure src is first for correct zataone import
src = Path(__file__).resolve().parent.parent / "src"
if str(src) not in sys.path:
    sys.path.insert(0, str(src))

import pytest

from fastapi.testclient import TestClient

from zataone.extractors.registry import ExtractorRegistry
from zataone.main import app
from zataone.models import Asset, Signal, Verdict
from zataone.storage.database import create_all_tables, get_session_factory

MINIMAL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def _make_mock_signal(extractor_id: str, signal_type: str = "keyword") -> SimpleNamespace:
    """Create a mock signal for persistence."""
    return SimpleNamespace(
        signal_type=signal_type,
        source_model=extractor_id,
        raw_data={"value": "guaranteed"},
        confidence=0.9,
    )


def _mock_load_extractors(self):
    """Replace domain extractors with mocks that return signals."""
    ext = MagicMock()
    ext.extractor_id = "ad_compliance_mock"
    ext.version = "1.0"
    ext.extract.return_value = [_make_mock_signal("ad_compliance_mock")]
    self._extractor_registry = ExtractorRegistry()
    self._extractor_registry.register(ext)


def _poll_until_completed(client: TestClient, asset_id: str, timeout_sec: float = 10.0) -> dict:
    """Poll GET /assets/{asset_id} until status is completed."""
    start = time.perf_counter()
    while (time.perf_counter() - start) < timeout_sec:
        resp = client.get(f"/assets/{asset_id}")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        if data.get("status") == "completed":
            return data
        time.sleep(0.1)
    pytest.fail(f"Asset {asset_id} did not complete within {timeout_sec}s")


@pytest.fixture(scope="module")
def db_setup():
    """Ensure DB is available, tables exist, and migrations are applied."""
    from sqlalchemy import text

    from zataone.storage.database import get_engine

    try:
        create_all_tables()
        # Apply migrations for existing DBs (status, idempotency_key)
        engine = get_engine()
        with engine.connect() as conn:
            for sql in [
                "ALTER TABLE assets ADD COLUMN IF NOT EXISTS status VARCHAR(32) DEFAULT 'processing'",
                "ALTER TABLE assets ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(255)",
            ]:
                try:
                    conn.execute(text(sql))
                    conn.commit()
                except Exception:
                    pass  # Column may already exist
    except Exception as e:
        pytest.skip(f"Database not available: {e}")


@patch("zataone.core.pipeline.CompliancePipeline._load_domain_extractors", _mock_load_extractors)
def test_upload_text_asset_creates_signals_verdict_and_persists(db_setup):
    """Upload text asset via POST /assets, verify signals, verdict, and DB persistence."""
    client = TestClient(app)

    resp = client.post(
        "/assets",
        json={"content": "Guaranteed instant cure", "type": "text"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "processing"
    asset_id = data["asset_id"]
    assert asset_id

    result = _poll_until_completed(client, asset_id)
    assert result["status"] == "completed"
    assert "verdict" in result
    assert "risk_score" in result
    assert "signals" in result
    assert "violations" in result
    assert len(result["signals"]) >= 1

    session = get_session_factory()()
    try:
        asset = session.query(Asset).filter(Asset.id == uuid.UUID(asset_id)).first()
        assert asset is not None
        assert asset.status == "completed"

        signals = session.query(Signal).filter(Signal.asset_id == uuid.UUID(asset_id)).all()
        assert len(signals) >= 1

        verdict = (
            session.query(Verdict)
            .filter(Verdict.asset_id == uuid.UUID(asset_id))
            .order_by(Verdict.created_at.desc())
            .first()
        )
        assert verdict is not None
        assert verdict.result.get("verdict") is not None
        assert "risk_score" in verdict.result
    finally:
        session.close()


@patch("zataone.core.pipeline.CompliancePipeline._load_domain_extractors", _mock_load_extractors)
def test_upload_image_asset_creates_signals_verdict_and_persists(db_setup):
    """Upload image asset via POST /assets/image, verify signals, verdict, and DB persistence."""
    client = TestClient(app)

    resp = client.post(
        "/assets/image",
        files={"file": ("test.png", MINIMAL_PNG, "image/png")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "processing"
    asset_id = data["asset_id"]
    assert asset_id

    result = _poll_until_completed(client, asset_id)
    assert result["status"] == "completed"
    assert "verdict" in result
    assert "risk_score" in result
    assert "signals" in result
    assert "violations" in result
    assert len(result["signals"]) >= 1

    session = get_session_factory()()
    try:
        asset = session.query(Asset).filter(Asset.id == uuid.UUID(asset_id)).first()
        assert asset is not None
        assert asset.status == "completed"
        assert asset.type == "image"

        signals = session.query(Signal).filter(Signal.asset_id == uuid.UUID(asset_id)).all()
        assert len(signals) >= 1

        verdict = (
            session.query(Verdict)
            .filter(Verdict.asset_id == uuid.UUID(asset_id))
            .order_by(Verdict.created_at.desc())
            .first()
        )
        assert verdict is not None
        assert verdict.result.get("verdict") is not None
        assert "risk_score" in verdict.result
    finally:
        session.close()
