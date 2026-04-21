"""Tests for API domain resolution (X-Domain + env)."""

import pytest
from fastapi import HTTPException


def test_resolve_domain_defaults(monkeypatch):
    monkeypatch.delenv("ZATAONE_DEFAULT_DOMAIN", raising=False)
    monkeypatch.delenv("ZATAONE_ALLOWED_DOMAINS", raising=False)
    from zataone.api.routes import _resolve_domain

    assert _resolve_domain(None) == "ad_compliance"
    assert _resolve_domain("") == "ad_compliance"
    assert _resolve_domain("ad_compliance") == "ad_compliance"


def test_resolve_domain_explicit_allowlist(monkeypatch):
    monkeypatch.setenv("ZATAONE_DEFAULT_DOMAIN", "ad_compliance")
    monkeypatch.setenv("ZATAONE_ALLOWED_DOMAINS", "ad_compliance,meta_pack")
    from zataone.api.routes import _resolve_domain

    assert _resolve_domain("meta_pack") == "meta_pack"
    assert _resolve_domain("META_PACK") == "meta_pack"


def test_resolve_domain_forbidden(monkeypatch):
    monkeypatch.setenv("ZATAONE_ALLOWED_DOMAINS", "ad_compliance")
    from zataone.api.routes import _resolve_domain

    with pytest.raises(HTTPException) as exc:
        _resolve_domain("unknown_domain")
    assert exc.value.status_code == 403


def test_resolve_domain_invalid_chars(monkeypatch):
    monkeypatch.delenv("ZATAONE_ALLOWED_DOMAINS", raising=False)
    from zataone.api.routes import _resolve_domain

    with pytest.raises(HTTPException) as exc:
        _resolve_domain("bad/domain")
    assert exc.value.status_code == 400


def test_enabled_domain_modalities():
    from zataone.core.pipeline import _enabled_domain_modalities

    assert _enabled_domain_modalities({}) is None
    assert _enabled_domain_modalities({"extractors": {}}) is None
    assert _enabled_domain_modalities({"extractors": {"enabled": []}}) is None
    assert _enabled_domain_modalities({"extractors": {"enabled": ["ocr", "asr"]}}) == {
        "ocr",
        "asr",
    }
