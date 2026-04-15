# zataone domain registry

from __future__ import annotations

from zataone.domains.base.domain_config import DomainConfig

DOMAIN_REGISTRY: dict[str, DomainConfig] = {}


def register_domain(domain_name: str, config: DomainConfig) -> None:
    """Register a domain configuration."""
    DOMAIN_REGISTRY[domain_name] = config


def get_domain_config(domain_name: str) -> DomainConfig:
    """Get domain configuration by name. Raises ValueError if not found."""
    if domain_name not in DOMAIN_REGISTRY:
        raise ValueError(f"Unknown domain: {domain_name}")
    return DOMAIN_REGISTRY[domain_name]
