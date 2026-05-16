# zataone legacy YAML rule -> DSL adapter

from __future__ import annotations

from typing import Any

from zataone.policy_engine.dsl.ast import MatchAST, MatchGroup, PatternSpec
from zataone.policy_engine.dsl.parser import parse_match_block


def rule_to_match_ast(rule: dict[str, Any]) -> MatchAST | None:
    """
    Build MatchAST from a rule dict.
    Uses explicit `match:` when present; otherwise converts legacy fields.
    """
    if rule.get("match"):
        return parse_match_block(rule["match"])

    if not any(
        rule.get(k)
        for k in (
            "prohibited_terms",
            "patterns",
            "context_terms",
            "exception_terms",
            "exception_patterns",
        )
    ):
        return None

    exceptions = None
    if rule.get("exception_terms") or rule.get("exception_patterns"):
        exceptions = MatchGroup(
            op="any",
            terms=[str(t) for t in rule.get("exception_terms") or []],
            patterns=_legacy_patterns(rule.get("exception_patterns")),
        )

    requires_context = None
    if rule.get("context_terms"):
        requires_context = MatchGroup(
            op="any",
            terms=[str(t) for t in rule["context_terms"]],
        )

    body_terms = [str(t) for t in rule.get("prohibited_terms") or []]
    body_patterns = _legacy_patterns(rule.get("patterns"))

    body = None
    if body_terms or body_patterns:
        body = MatchGroup(
            op="any",
            terms=body_terms,
            patterns=body_patterns,
        )

    return MatchAST(exceptions=exceptions, requires_context=requires_context, body=body)


def _legacy_patterns(raw: Any) -> list[PatternSpec]:
    if not raw:
        return []
    specs: list[PatternSpec] = []
    for item in raw:
        if isinstance(item, str):
            specs.append(PatternSpec(pattern=item))
        elif isinstance(item, dict) and item.get("pattern"):
            specs.append(
                PatternSpec(
                    pattern=str(item["pattern"]),
                    confidence=float(item.get("confidence", 0.9)),
                    description=str(item.get("description", "")),
                )
            )
    return specs
