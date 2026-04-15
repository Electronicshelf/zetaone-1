"""
Unit tests for domain registry.
"""

import sys
from pathlib import Path

# Ensure src is first for correct zataone import
src = Path(__file__).resolve().parent.parent / "src"
if str(src) not in sys.path:
    sys.path.insert(0, str(src))

import pytest

from zataone.domains.base.domain_config import DomainConfig
from zataone.domains.registry import (
    DOMAIN_REGISTRY,
    get_domain_config,
    register_domain,
)


def test_register_domain():
    """register_domain stores config in DOMAIN_REGISTRY."""
    # Clear registry to avoid pollution from other tests
    DOMAIN_REGISTRY.clear()

    config = DomainConfig(
        name="test_domain",
        extractors=[],
        policy_pack_path="/path/to/policies.yaml",
        config_path="/path/to/config.yaml",
        mappings_path="/path/to/mappings",
    )
    register_domain("test_domain", config)

    assert "test_domain" in DOMAIN_REGISTRY
    assert DOMAIN_REGISTRY["test_domain"] is config
    assert DOMAIN_REGISTRY["test_domain"].name == "test_domain"
    assert DOMAIN_REGISTRY["test_domain"].policy_pack_path == "/path/to/policies.yaml"


def test_get_domain_config():
    """get_domain_config returns registered config."""
    DOMAIN_REGISTRY.clear()

    config = DomainConfig(
        name="my_domain",
        extractors=[object],
        policy_pack_path="/policies",
        config_path="/config",
    )
    register_domain("my_domain", config)

    result = get_domain_config("my_domain")
    assert result is config
    assert result.name == "my_domain"
    assert result.extractors == [object]


def test_get_domain_config_unknown_raises():
    """get_domain_config raises ValueError for unknown domain."""
    DOMAIN_REGISTRY.clear()

    with pytest.raises(ValueError, match="Unknown domain: nonexistent"):
        get_domain_config("nonexistent")
