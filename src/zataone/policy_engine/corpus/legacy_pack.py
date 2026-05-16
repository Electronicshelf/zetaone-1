# zataone legacy rules-only YAML -> PolicyPack

from __future__ import annotations

from typing import Any

from zataone.policy_engine.corpus.models import PolicyClause, PolicyPack, PolicyVersion


def synthesize_pack_from_rules(
    rules: dict[str, Any],
    *,
    source_path: str | None = None,
    pack_id: str = "legacy",
) -> PolicyPack:
    """Build a minimal PolicyPack when YAML has only `rules:` (no policy_pack header)."""
    clauses: list[PolicyClause] = []
    for rule_id, rule in rules.items():
        desc = str(rule.get("description", rule.get("name", rule_id)))
        modalities = ["text"]
        if rule.get("vision_primary_labels"):
            modalities.append("image")
        clauses.append(
            PolicyClause(
                clause_id=f"legacy.{rule_id}",
                text=desc,
                modalities=modalities,
                rule_ids=[rule_id],
            )
        )
    return PolicyPack(
        id=pack_id,
        platform="meta",
        jurisdiction="US",
        version=PolicyVersion(version="0.0.0", effective_date=None),
        modalities=["text", "image"],
        clauses=clauses,
        rules=rules,
        source_path=source_path,
    )
