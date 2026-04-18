"""
Test POST /assets/image endpoint.
Uses mocked pipeline to avoid real OCR/ML.
Requires: pip install httpx (for FastAPI TestClient)
"""

import base64
import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure src is first for correct zataone import
src = Path(__file__).resolve().parent.parent / "src"
if str(src) not in sys.path:
    sys.path.insert(0, str(src))

from fastapi.testclient import TestClient

from zataone.main import app

# Minimal 1x1 PNG (valid image bytes)
MINIMAL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)

MOCK_VERDICT = {
    "verdict": "likely_approved",
    "risk_score": 0.0,
    "status": "COMPLIANT",
    "violations": [],
    "signals": [],
    "fix_suggestions": [],
    "metadata": {},
}


def test_post_assets_image():
    """POST /assets/image returns 200 with status processing and asset_id."""
    mock_session = MagicMock()
    with (
        patch("zataone.api.routes.get_session_factory") as mock_sf,
        patch("zataone.api.routes.IngestionService") as MockIngestion,
    ):
        mock_sf.return_value.return_value = mock_session
        mock_ingestion = MockIngestion.return_value
        mock_ingestion.create_asset_stub.return_value = None

        client = TestClient(app)
        response = client.post(
            "/assets/image",
            files={"file": ("test.png", MINIMAL_PNG, "image/png")},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processing"
    assert "asset_id" in data


def test_post_assets_image_idempotency_returns_existing():
    """POST /assets/image with Idempotency-Key returns existing verdict when found."""
    existing_verdict = {
        "verdict": "likely_rejected",
        "risk_score": 0.9,
        "status": "NON_COMPLIANT",
        "violations": [{"rule_id": "test"}],
        "signals": [],
        "fix_suggestions": [],
        "metadata": {},
    }
    mock_session = MagicMock()
    with (
        patch("zataone.api.routes.get_session_factory") as mock_sf,
        patch("zataone.api.routes.IngestionService") as MockIngestion,
    ):
        mock_sf.return_value.return_value = mock_session
        mock_instance = MockIngestion.return_value
        mock_instance.find_existing_verdict.return_value = (
            uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"),
            existing_verdict,
        )

        client = TestClient(app)
        response = client.post(
            "/assets/image",
            files={"file": ("test.png", MINIMAL_PNG, "image/png")},
            headers={"Idempotency-Key": "test-key-123"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["verdict"] == "likely_rejected"
    assert data["risk_score"] == 0.9
    assert data["asset_id"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    mock_instance.find_existing_verdict.assert_called_once_with(
        mock_session, "test-key-123", tenant_id=None
    )
