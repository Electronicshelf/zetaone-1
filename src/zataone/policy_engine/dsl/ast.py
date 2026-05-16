# zataone policy DSL AST

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PatternSpec:
    pattern: str
    confidence: float = 0.9
    description: str = ""


@dataclass
class MatchAST:
    """
    Deterministic rule match tree.

    Evaluation order: exceptions (NOT) -> requires_context (ALL) -> body (any/all).
    """

    exceptions: "MatchGroup | None" = None
    requires_context: "MatchGroup | None" = None
    body: "MatchGroup | None" = None


@dataclass
class MatchGroup:
    """Group of conditions with ANY or ALL semantics."""

    op: str  # "any" | "all"
    terms: list[str] = field(default_factory=list)
    term_confidence: float = 0.9
    patterns: list[PatternSpec] = field(default_factory=list)
    children: list["MatchGroup"] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.terms and not self.patterns and not self.children
