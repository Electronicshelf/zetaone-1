# zataone domain configuration

from __future__ import annotations

from typing import Any


class DomainConfig:
    """Configuration for a compliance domain."""

    def __init__(
        self,
        name: str,
        extractors: list[Any],
        policy_pack_path: str,
        config_path: str,
        mappings_path: str | None = None,
    ) -> None:
        self.name = name
        self.extractors = extractors
        self.policy_pack_path = policy_pack_path
        self.config_path = config_path
        self.mappings_path = mappings_path
