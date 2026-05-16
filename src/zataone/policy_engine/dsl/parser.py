# zataone policy DSL YAML parser

from __future__ import annotations

from typing import Any

from zataone.policy_engine.dsl.ast import MatchAST, MatchGroup, PatternSpec


def parse_match_block(match: dict[str, Any] | None) -> MatchAST | None:
    """Parse a rule's `match:` YAML block into MatchAST."""
    if not match or not isinstance(match, dict):
        return None

    exceptions_raw = match.get("exceptions") or match.get("not")
    requires_raw = match.get("requires_context")
    body_raw = match.get("match") or match.get("any") or match.get("all")

    ast = MatchAST(
        exceptions=_parse_exception_group(exceptions_raw),
        requires_context=_parse_context_group(requires_raw),
        body=_parse_body(body_raw, match),
    )
    return ast


def _parse_exception_group(raw: Any) -> MatchGroup | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return MatchGroup(
            op="any",
            terms=list(raw.get("terms") or raw.get("exception_terms") or []),
            patterns=_parse_patterns(raw.get("patterns") or raw.get("exception_patterns")),
        )
    if isinstance(raw, list):
        return MatchGroup(op="any", terms=[str(x) for x in raw])
    return None


def _parse_context_group(raw: Any) -> MatchGroup | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        terms = raw.get("terms") or raw.get("context_terms") or []
        return MatchGroup(op="any", terms=[str(t) for t in terms])
    if isinstance(raw, list):
        return MatchGroup(op="any", terms=[str(t) for t in raw])
    return None


def _parse_body(body_raw: Any, parent: dict[str, Any]) -> MatchGroup | None:
    if body_raw is not None:
        if isinstance(body_raw, dict):
            return _parse_group_dict(body_raw)
        if isinstance(body_raw, list):
            return MatchGroup(op="any", children=[_parse_group_item(item) for item in body_raw])
    if "any" in parent:
        raw = parent["any"]
        if isinstance(raw, list):
            return MatchGroup(op="any", children=[_parse_group_item(item) for item in raw])
        return _parse_group_dict(raw) if isinstance(raw, dict) else None
    if "all" in parent:
        raw = parent["all"]
        if isinstance(raw, list):
            return MatchGroup(op="all", children=[_parse_group_item(item) for item in raw])
        return _parse_group_dict(raw) if isinstance(raw, dict) else None
  # single leaf at top level
    if any(k in parent for k in ("terms", "patterns", "prohibited_terms")):
        return _parse_group_dict(parent)
    return None


def _parse_group_item(item: Any) -> MatchGroup:
    if isinstance(item, dict):
        return _parse_group_dict(item)
    return MatchGroup(op="any", terms=[str(item)])


def _parse_group_dict(d: dict[str, Any]) -> MatchGroup:
    op = "all" if d.get("all") is True or "all" in d and isinstance(d.get("all"), list) else "any"
    if "all" in d and isinstance(d["all"], list):
        return MatchGroup(
            op="all",
            children=[_parse_group_item(x) for x in d["all"]],
        )
    if "any" in d and isinstance(d["any"], list):
        return MatchGroup(
            op="any",
            children=[_parse_group_item(x) for x in d["any"]],
        )
    terms = d.get("terms") or d.get("prohibited_terms") or []
    patterns = _parse_patterns(d.get("patterns"))
    children = []
    for key in ("any", "all"):
        if key in d and isinstance(d[key], list) and key != op:
            children.extend(_parse_group_item(x) for x in d[key])
    return MatchGroup(
        op=op,
        terms=[str(t) for t in terms],
        term_confidence=float(d.get("term_confidence", 0.9)),
        patterns=patterns,
        children=children,
    )


def _parse_patterns(raw: Any) -> list[PatternSpec]:
    if not raw:
        return []
    specs: list[PatternSpec] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str):
                specs.append(PatternSpec(pattern=item))
            elif isinstance(item, dict):
                specs.append(
                    PatternSpec(
                        pattern=str(item.get("pattern", "")),
                        confidence=float(item.get("confidence", 0.9)),
                        description=str(item.get("description", "")),
                    )
                )
    return [p for p in specs if p.pattern]
