"""Explainability graph includes document snapshot from verdict metadata."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

src = Path(__file__).resolve().parent.parent / "src"
if str(src) not in sys.path:
    sys.path.insert(0, str(src))

from zataone.explainability.graph_builder import build_explainability_graph
from zataone.models import Asset, Verdict


@pytest.mark.skipif(
    not __import__("os").environ.get("DATABASE_URL"),
    reason="DATABASE_URL required for DB explainability tests",
)
def test_graph_includes_document_from_verdict_metadata(db_session):
    asset = Asset(
        id=uuid.uuid4(),
        type="text",
        status="completed",
        content_hash="hash-doc",
    )
    db_session.add(asset)
    db_session.flush()

    verdict = Verdict(
        asset_id=asset.id,
        status="REVIEW_REQUIRED",
        risk_score=0.5,
        result={
            "verdict": "borderline",
            "risk_score": 0.5,
            "status": "REVIEW_REQUIRED",
            "metadata": {
                "document": {
                    "asset_id": str(asset.id),
                    "modality": "text",
                    "normalized_text": "guaranteed cure",
                    "source_signal_ids": [],
                    "spans": [],
                    "scene_descriptions": [],
                    "timeline": [],
                    "metadata": {},
                },
                "document_centric_enabled": False,
            },
        },
    )
    db_session.add(verdict)
    db_session.commit()

    graph = build_explainability_graph(asset.id, db_session)
    assert graph["document"] is not None
    assert graph["document"]["normalized_text"] == "guaranteed cure"
    assert graph["document_centric_enabled"] is False


def test_graph_document_none_without_metadata():
    """Unit-level: graph builder handles missing document gracefully."""

    class FakeVerdict:
        result = {"verdict": "likely_approved", "metadata": {}}

    class FakeQuery:
        def filter(self, *args, **kwargs):
            return self

        def order_by(self, *args, **kwargs):
            return self

        def first(self):
            return FakeVerdict()

        def all(self):
            return []

    class FakeSession:
        def query(self, model):
            return FakeQuery()

    graph = build_explainability_graph(uuid.uuid4(), FakeSession())  # type: ignore[arg-type]
    assert graph["document"] is None
