"""Unit tests for policy DSL evaluator."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

src = Path(__file__).resolve().parent.parent / "src"
if str(src) not in sys.path:
    sys.path.insert(0, str(src))

from zataone.policy_engine.dsl.ast import MatchAST, MatchGroup, PatternSpec
from zataone.policy_engine.dsl.evaluator import RuleEvaluator
from zataone.policy_engine.dsl.legacy_adapter import rule_to_match_ast
from zataone.policy_engine.dsl.parser import parse_match_block
from zataone.policy_engine.normalize import normalize_for_matching


def test_normalize_lowercase():
    assert normalize_for_matching("  Hello  WORLD ") == "hello world"


def test_any_terms_match():
    ast = MatchAST(
        body=MatchGroup(
            op="any",
            terms=["guaranteed", "miracle"],
        )
    )
    hit = RuleEvaluator.evaluate("This is guaranteed to work", ast)
    assert hit is not None
    assert hit.matched_term.lower() == "guaranteed"
    assert hit.span is not None


def test_requires_context_any_term():
    ast = MatchAST(
        requires_context=MatchGroup(op="any", terms=["pain", "chronic"]),
        body=MatchGroup(op="any", terms=["cure"]),
    )
    assert RuleEvaluator.evaluate("cure pain fast", ast) is not None
    assert RuleEvaluator.evaluate("cure fast", ast) is None


def test_exceptions_suppress_match():
    match = {
        "exceptions": {
            "terms": ["for fun"],
            "patterns": [r"\bno\s+real\s+money\b"],
        },
        "any": [{"terms": ["casino", "betting"]}],
    }
    ast = parse_match_block(match)
    assert RuleEvaluator.evaluate("casino for fun", ast) is None
    assert RuleEvaluator.evaluate("casino real money", ast) is not None


def test_pattern_phrase_span():
    ast = MatchAST(
        body=MatchGroup(
            op="any",
            patterns=[
                PatternSpec(
                    pattern=r"lose\s+\d+\s+pounds?\s+in\s+\d+\s+days?",
                    confidence=0.95,
                )
            ],
        )
    )
    text = "lose 10 pounds in 5 days"
    hit = RuleEvaluator.evaluate(text, ast, original_text=text)
    assert hit is not None
    assert hit.span["start"] == 0
    assert "10" in hit.span["text"]


def test_legacy_adapter_equivalence_terms():
    rule = {
        "prohibited_terms": ["guaranteed"],
        "patterns": [{"pattern": r"instant", "confidence": 0.9}],
    }
    ast = rule_to_match_ast(rule)
    assert ast is not None
    assert RuleEvaluator.evaluate("instant approval", ast) is not None
