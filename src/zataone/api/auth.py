# zataone request authentication

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import Header, HTTPException, status

from zataone.services.api_key_service import APIKeyService
from zataone.storage.database import get_session_factory


def _auth_enabled() -> bool:
    """
    Auth is ON when ZATAONE_AUTH_ENABLED=1, or when running on Cloud Run (K_SERVICE set)
    and ZATAONE_AUTH_ENABLED is not explicitly disabled.
    Off by default in local dev (no K_SERVICE, no explicit flag).
    """
    v = os.environ.get("ZATAONE_AUTH_ENABLED", "").strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    if v in ("0", "false", "no", "off"):
        return False
    # Auto-enable on Cloud Run.
    return bool(os.environ.get("K_SERVICE", "").strip())


@dataclass
class AuthContext:
    """Resolved auth state injected into route handlers."""
    tenant_id: uuid.UUID | None
    api_key_id: uuid.UUID | None
    authenticated: bool


_svc = APIKeyService()


def get_auth_context(
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    x_tenant_id: str | None = Header(None, alias="X-Tenant-ID"),
) -> AuthContext:
    """
    FastAPI dependency. Validates X-API-Key when auth is enabled.

    When auth is disabled (local dev): passes through using X-Tenant-ID header,
    so existing callers and the PolicyLens UI keep working unchanged.

    Raises 401 if auth is enabled and the key is missing or invalid.
    """
    if not _auth_enabled():
        tid: uuid.UUID | None = None
        if x_tenant_id:
            try:
                tid = uuid.UUID(x_tenant_id)
            except ValueError:
                pass
        return AuthContext(tenant_id=tid, api_key_id=None, authenticated=False)

    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    session = get_session_factory()()
    try:
        record = _svc.validate_key(session, x_api_key)
        session.commit()
    finally:
        session.close()

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return AuthContext(
        tenant_id=record.tenant_id,
        api_key_id=record.id,
        authenticated=True,
    )
