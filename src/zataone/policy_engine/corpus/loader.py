# zataone policy pack loader

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from zataone.policy_engine.corpus.legacy_pack import synthesize_pack_from_rules
from zataone.policy_engine.corpus.models import PolicyClause, PolicyPack, PolicyVersion


def load_policy_pack_from_dict(
    data: dict[str, Any],
    *,
    source_path: str | None = None,
    platform: str | None = None,
    jurisdiction: str | None = None,
) -> PolicyPack:
    """Load PolicyPack from parsed YAML dict."""
    rules = data.get("rules") or {}
    if not rules:
        raise ValueError("Policy YAML contains no rules")

    pack_meta = data.get("policy_pack") or {}
    pack_id = str(pack_meta.get("id", "meta_ads_legacy"))
    pack_platform = str(platform or pack_meta.get("platform", "meta"))
    pack_jurisdiction = str(jurisdiction or pack_meta.get("jurisdiction", "US"))
    version_str = str(pack_meta.get("version", "0.0.0"))
    effective = pack_meta.get("effective_date")
    modalities = list(pack_meta.get("modalities") or ["text", "image"])

    clauses_raw = data.get("clauses") or []
    clauses: list[PolicyClause] = []
    for item in clauses_raw:
        if not isinstance(item, dict) or not item.get("clause_id"):
            continue
        clauses.append(
            PolicyClause(
                clause_id=str(item["clause_id"]),
                text=str(item.get("text", "")),
                modalities=list(item.get("modalities") or ["text"]),
                rule_ids=[str(r) for r in item.get("rule_ids") or []],
                tags=[str(t) for t in item.get("tags") or []],
            )
        )

    if not clauses:
        return synthesize_pack_from_rules(
            rules,
            source_path=source_path,
            pack_id=pack_id,
        )

    return PolicyPack(
        id=pack_id,
        platform=pack_platform,
        jurisdiction=pack_jurisdiction,
        version=PolicyVersion(version=version_str, effective_date=str(effective) if effective else None),
        modalities=modalities,
        clauses=clauses,
        rules=rules,
        source_path=source_path,
    )


def load_policy_pack_from_path(
    path: str | Path,
    *,
    platform: str | None = None,
    jurisdiction: str | None = None,
) -> PolicyPack:
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return load_policy_pack_from_dict(
        data,
        source_path=str(path),
        platform=platform,
        jurisdiction=jurisdiction,
    )
