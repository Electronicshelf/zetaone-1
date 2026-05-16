# zataone policy retrieval (BM25 shortlist)

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from zataone.policy_engine.corpus.models import PolicyPack
from zataone.policy_engine.retrieval.bm25 import BM25Index
from zataone.policy_engine.retrieval.flags import (
    policy_retrieval_enabled,
    retrieval_fallback_all,
    retrieval_top_k,
)


@dataclass
class RetrievalResult:
    retrieved_rule_ids: list[str] = field(default_factory=list)
    retrieved_clause_ids: list[str] = field(default_factory=list)
    retrieval_scores: dict[str, float] = field(default_factory=dict)
    method: str = "bm25"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PolicyRetriever:
    """
    Lexical retrieval over policy clauses and rule text.
    Non-binding: deterministic engine evaluates only the shortlist.
    """

    def __init__(self, pack: PolicyPack) -> None:
        self._pack = pack
        self._documents = self._build_documents(pack)
        self._index = BM25Index(self._documents) if self._documents else None
        self._clause_by_rule: dict[str, list[str]] = {}
        for clause in pack.clauses:
            for rid in clause.rule_ids:
                self._clause_by_rule.setdefault(rid, []).append(clause.clause_id)

    @staticmethod
    def _build_documents(pack: PolicyPack) -> dict[str, str]:
        docs: dict[str, str] = {}
        for clause in pack.clauses:
            docs[f"clause:{clause.clause_id}"] = clause.text
        for rule_id, rule in pack.rules.items():
            parts = [
                str(rule.get("name", "")),
                str(rule.get("description", "")),
                " ".join(str(t) for t in rule.get("prohibited_terms") or []),
            ]
            match = rule.get("match")
            if isinstance(match, dict):
                parts.append(str(match))
            docs[f"rule:{rule_id}"] = " ".join(p for p in parts if p)
        return docs

    def retrieve(self, query_text: str, *, vision_rule_ids: set[str] | None = None) -> RetrievalResult:
        if not policy_retrieval_enabled() or self._index is None:
            return RetrievalResult(
                retrieved_rule_ids=list(self._pack.rules.keys()),
                method="all_rules",
            )

        top_k = retrieval_top_k()
        ranked = self._index.query(query_text or "", top_k=top_k * 2)

        rule_scores: dict[str, float] = {}
        clause_scores: dict[str, float] = {}
        for doc_id, score in ranked:
            if doc_id.startswith("rule:"):
                rid = doc_id.split(":", 1)[1]
                rule_scores[rid] = max(rule_scores.get(rid, 0.0), score)
            elif doc_id.startswith("clause:"):
                cid = doc_id.split(":", 1)[1]
                clause_scores[cid] = score
                for clause in self._pack.clauses:
                    if clause.clause_id == cid:
                        for rid in clause.rule_ids:
                            rule_scores[rid] = max(rule_scores.get(rid, 0.0), score)

        sorted_rules = sorted(rule_scores.items(), key=lambda x: x[1], reverse=True)
        retrieved_rules = [rid for rid, _ in sorted_rules[:top_k]]

        if vision_rule_ids:
            for rid in vision_rule_ids:
                if rid not in retrieved_rules:
                    retrieved_rules.append(rid)

        if not retrieved_rules and retrieval_fallback_all():
            retrieved_rules = list(self._pack.rules.keys())

        retrieved_clauses = [
            cid for cid, _ in sorted(clause_scores.items(), key=lambda x: x[1], reverse=True)
        ][:top_k]

        return RetrievalResult(
            retrieved_rule_ids=retrieved_rules,
            retrieved_clause_ids=retrieved_clauses,
            retrieval_scores={rid: rule_scores.get(rid, 0.0) for rid in retrieved_rules},
            method="bm25",
        )
