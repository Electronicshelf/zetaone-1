# zataone policy DSL evaluator

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from zataone.policy_engine.dsl.ast import MatchAST, MatchGroup, PatternSpec
from zataone.policy_engine.normalize import normalize_for_matching


@dataclass(frozen=True)
class DSLMatchResult:
    """Deterministic DSL match outcome."""

    matched_term: str
    confidence: float
    span: dict[str, Any] | None = None
    match_kind: str = "term"  # term | pattern


class RuleEvaluator:
    """Evaluate MatchAST against document text (phrase-aware on full string)."""

    @classmethod
    def evaluate(
        cls,
        text: str,
        ast: MatchAST | None,
        *,
        original_text: str | None = None,
    ) -> DSLMatchResult | None:
        if ast is None:
            return None
        norm = normalize_for_matching(text)
        display = original_text if original_text is not None else text
        if ast.exceptions and cls._group_matches(norm, ast.exceptions):
            return None
        if ast.requires_context and not cls._context_satisfied(norm, ast.requires_context):
            return None
        if ast.body is None:
            return None
        return cls._eval_group(norm, display, ast.body)

    @classmethod
    def _group_matches(cls, norm: str, group: MatchGroup) -> bool:
        """True if exception group matches (any term/pattern/child)."""
        return cls._eval_group(norm, norm, group) is not None

    @classmethod
    def _context_satisfied(cls, norm: str, group: MatchGroup) -> bool:
        """Requires at least one context term (legacy context_terms semantics)."""
        if group.terms:
            return any(t.lower() in norm for t in group.terms)
        for child in group.children:
            if cls._context_satisfied(norm, child):
                return True
        return not group.terms and not group.children

    @classmethod
    def _group_satisfied_all(cls, norm: str, group: MatchGroup) -> bool:
        if group.terms:
            if not all(t.lower() in norm for t in group.terms):
                return False
        for child in group.children:
            if not cls._group_satisfied_all(norm, child):
                return False
        return True if group.terms or group.children else True

    @classmethod
    def _eval_group(cls, norm: str, display: str, group: MatchGroup) -> DSLMatchResult | None:
        if group.op == "all":
            return cls._eval_all(norm, display, group)
        return cls._eval_any(norm, display, group)

    @classmethod
    def _eval_any(cls, norm: str, display: str, group: MatchGroup) -> DSLMatchResult | None:
        for pat in group.patterns:
            hit = cls._match_pattern(display, norm, pat)
            if hit:
                return hit
        for term in group.terms:
            hit = cls._match_term(display, norm, term, group.term_confidence)
            if hit:
                return hit
        for child in group.children:
            hit = cls._eval_group(norm, display, child)
            if hit:
                return hit
        return None

    @classmethod
    def _eval_all(cls, norm: str, display: str, group: MatchGroup) -> DSLMatchResult | None:
        if group.terms:
            for term in group.terms:
                if term.lower() not in norm:
                    return None
        hits: list[DSLMatchResult] = []
        for pat in group.patterns:
            hit = cls._match_pattern(display, norm, pat)
            if not hit:
                return None
            hits.append(hit)
        for child in group.children:
            hit = cls._eval_group(norm, display, child)
            if not hit:
                return None
            hits.append(hit)
        if hits:
            return hits[0]
        if group.terms:
            first = group.terms[0]
            return cls._match_term(display, norm, first, group.term_confidence)
        return None

    @staticmethod
    def _match_pattern(display: str, norm: str, spec: PatternSpec) -> DSLMatchResult | None:
        match = re.search(spec.pattern, display, re.IGNORECASE)
        if not match:
            match = re.search(spec.pattern, norm, re.IGNORECASE)
        if not match:
            return None
        return DSLMatchResult(
            matched_term=match.group(0),
            confidence=spec.confidence,
            span={"start": match.start(), "end": match.end(), "text": match.group(0)},
            match_kind="pattern",
        )

    @staticmethod
    def _match_term(
        display: str,
        norm: str,
        term: str,
        default_confidence: float,
    ) -> DSLMatchResult | None:
        term_lower = term.lower()
        idx = norm.find(term_lower)
        if idx < 0:
            return None
        padded = f" {norm} "
        conf = 0.95 if f" {term_lower} " in padded else 0.85
        if conf < default_confidence:
            conf = default_confidence
        span_text = display[idx : idx + len(term)] if idx + len(term) <= len(display) else term
        if idx < len(display):
            span_text = display[idx : min(idx + len(term), len(display))]
        return DSLMatchResult(
            matched_term=term,
            confidence=conf,
            span={"start": idx, "end": idx + len(term_lower), "text": span_text},
            match_kind="term",
        )
