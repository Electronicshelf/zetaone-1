"""BM25 policy retrieval tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

src = Path(__file__).resolve().parent.parent / "src"
if str(src) not in sys.path:
    sys.path.insert(0, str(src))

from zataone.policy_engine.corpus.loader import load_policy_pack_from_path
from zataone.policy_engine.retrieval.retriever import PolicyRetriever


@pytest.fixture
def meta_pack():
    path = (
        Path(__file__).resolve().parent.parent
        / "src/zataone/domains/ad_compliance/policies/meta_ads.yaml"
    )
    return load_policy_pack_from_path(path)


def test_retrieval_ranks_gambling_for_casino_query(meta_pack, monkeypatch):
    monkeypatch.setenv("ZATAONE_POLICY_RETRIEVAL", "true")
    retriever = PolicyRetriever(meta_pack)
    result = retriever.retrieve("betting casino sportsbook real money wager")
    assert "gambling" in result.retrieved_rule_ids
    assert result.retrieval_scores.get("gambling", 0) > 0


def test_retrieval_shortlist_smaller_than_all_rules(meta_pack, monkeypatch):
    monkeypatch.setenv("ZATAONE_RETRIEVAL_TOP_K", "3")
    monkeypatch.setenv("ZATAONE_POLICY_RETRIEVAL", "true")
    retriever = PolicyRetriever(meta_pack)
    result = retriever.retrieve("guaranteed miracle instant")
    assert len(result.retrieved_rule_ids) <= 3


def test_retrieval_includes_vision_primary(meta_pack):
    retriever = PolicyRetriever(meta_pack)
    result = retriever.retrieve(
        "neutral product",
        vision_rule_ids={"weapons_ammunition_explosives"},
    )
    assert "weapons_ammunition_explosives" in result.retrieved_rule_ids
