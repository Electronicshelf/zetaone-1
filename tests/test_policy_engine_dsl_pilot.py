"""Pilot DSL rules + document-centric integration."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

src = Path(__file__).resolve().parent.parent / "src"
if str(src) not in sys.path:
    sys.path.insert(0, str(src))

from zataone.document.builder import DocumentBuilder
from zataone.policy_engine.corpus.loader import load_policy_pack_from_path
from zataone.policy_engine.engine import PolicyEngine
from zataone.policy_engine.retrieval.flags import policy_retrieval_enabled
from zataone.policy_engine.retrieval.retriever import PolicyRetriever


@pytest.fixture
def engine_with_pack():
    path = (
        Path(__file__).resolve().parent.parent
        / "src/zataone/domains/ad_compliance/policies/meta_ads.yaml"
    )
    pack = load_policy_pack_from_path(path)
    engine = PolicyEngine()
    engine.load_policy_pack(rules=pack.rules)
    return engine, pack


def test_gambling_exception_free_to_play(engine_with_pack, monkeypatch):
    monkeypatch.setenv("ZATAONE_DOCUMENT_CENTRIC", "true")
    engine, _ = engine_with_pack
    document = DocumentBuilder.build(
        SimpleNamespace(type="text", content="Play poker for fun with no real money"),
        [],
    )
    violations = engine.evaluate([], document=document)
    gambling = [v for v in violations if v.rule_id == "gambling"]
    assert len(gambling) == 0


def test_gambling_matches_casino(engine_with_pack, monkeypatch):
    monkeypatch.setenv("ZATAONE_DOCUMENT_CENTRIC", "true")
    engine, _ = engine_with_pack
    document = DocumentBuilder.build(
        SimpleNamespace(type="text", content="Join our online casino today"),
        [],
    )
    violations = engine.evaluate([], document=document)
    assert any(v.rule_id == "gambling" for v in violations)


def test_retrieval_limits_rules_evaluated(engine_with_pack, monkeypatch):
    monkeypatch.setenv("ZATAONE_DOCUMENT_CENTRIC", "true")
    monkeypatch.setenv("ZATAONE_POLICY_RETRIEVAL", "true")
    monkeypatch.setenv("ZATAONE_RETRIEVAL_TOP_K", "2")
    engine, pack = engine_with_pack
    retriever = PolicyRetriever(pack)
    doc_text = "guaranteed miracle instant overnight"
    retrieval = retriever.retrieve(doc_text)
    engine.set_active_rule_ids(retrieval.retrieved_rule_ids)
    document = DocumentBuilder.build(
        SimpleNamespace(type="text", content=doc_text),
        [],
    )
    violations = engine.evaluate([], document=document)
    rule_ids_hit = {v.rule_id for v in violations}
    assert rule_ids_hit.issubset(set(retrieval.retrieved_rule_ids) | set())


def test_medical_requires_context(engine_with_pack, monkeypatch):
    monkeypatch.setenv("ZATAONE_DOCUMENT_CENTRIC", "true")
    engine, _ = engine_with_pack
    doc_no_ctx = DocumentBuilder.build(
        SimpleNamespace(type="text", content="We cure everything"),
        [],
    )
    doc_ctx = DocumentBuilder.build(
        SimpleNamespace(type="text", content="Heal chronic back pain with our cure"),
        [],
    )
    v1 = engine.evaluate([], document=doc_no_ctx)
    v2 = engine.evaluate([], document=doc_ctx)
    assert not any(v.rule_id == "medical_health_claims" for v in v1)
    assert any(v.rule_id == "medical_health_claims" for v in v2)
