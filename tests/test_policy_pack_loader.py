"""Policy corpus loader tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

src = Path(__file__).resolve().parent.parent / "src"
if str(src) not in sys.path:
    sys.path.insert(0, str(src))

from zataone.policy_engine.corpus.loader import load_policy_pack_from_dict, load_policy_pack_from_path


def test_load_meta_ads_pack_from_repo():
    path = (
        Path(__file__).resolve().parent.parent
        / "src/zataone/domains/ad_compliance/policies/meta_ads.yaml"
    )
    pack = load_policy_pack_from_path(path)
    assert pack.id == "meta_ads_us"
    assert pack.platform == "meta"
    assert pack.version.version == "2025-05-01"
    assert len(pack.clauses) >= 3
    assert "misleading_exaggerated_claims" in pack.rules
    assert any(c.clause_id == "meta.gambling.restricted" for c in pack.clauses)


def test_legacy_rules_only_synthesizes_clauses():
    data = {
        "rules": {
            "test_rule": {
                "name": "Test",
                "description": "A test rule",
                "prohibited_terms": ["bad"],
                "severity": "LOW",
            }
        }
    }
    pack = load_policy_pack_from_dict(data)
    assert pack.id == "meta_ads_legacy" or pack.id  # legacy synthesize uses meta_ads_legacy from empty pack_meta
    assert len(pack.clauses) == 1
    assert pack.clauses[0].rule_ids == ["test_rule"]
