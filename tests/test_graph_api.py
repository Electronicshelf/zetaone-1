"""
Test GET /assets/{asset_id}/graph endpoint.
Verifies response contains asset, signals, violations, evidence, verdict.
"""

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
from zataone.storage.database import create_all_tables


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
def test_get_asset_graph_returns_full_evidence_graph(db_setup):
    """GET /assets/{asset_id}/graph returns asset, signals, violations, evidence, verdict."""
    client = TestClient(app)

    resp = client.post(
        "/assets",
        json={"content": "Guaranteed instant cure", "type": "text"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "processing"
    asset_id = data["asset_id"]

    _poll_until_completed(client, asset_id)

    graph_resp = client.get(f"/assets/{asset_id}/graph")
    assert graph_resp.status_code == 200
    graph = graph_resp.json()

    assert "asset" in graph
    assert "signals" in graph
    assert "violations" in graph
    assert "evidence" in graph
    assert "verdict" in graph

    assert isinstance(graph["signals"], list)
    assert isinstance(graph["violations"], list)
    assert isinstance(graph["evidence"], list)
    assert isinstance(graph["verdict"], dict)

    assert graph["asset"]["id"] == asset_id
    assert len(graph["signals"]) >= 1
    assert graph["verdict"]  # non-empty when completed


def test_get_asset_graph_404_when_asset_not_found():
    """GET /assets/{asset_id}/graph returns 404 when asset does not exist."""
    mock_session = MagicMock()
    mock_query = MagicMock()
    mock_filter = MagicMock()
    mock_filter.first.return_value = None
    mock_query.filter.return_value = mock_filter
    mock_session.query.return_value = mock_query

    with patch("zataone.api.routes.get_session_factory") as mock_sf:
        mock_sf.return_value.return_value = mock_session
        client = TestClient(app)
        fake_id = str(uuid.uuid4())
        resp = client.get(f"/assets/{fake_id}/graph")

    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()
