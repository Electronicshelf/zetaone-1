# zataone admin routes — tenant and API key management
#
# All endpoints require X-Admin-Secret header matching ZATAONE_ADMIN_SECRET env var.
# If ZATAONE_ADMIN_SECRET is not set, all admin endpoints return 503.

from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from zataone.models.tenant import Tenant
from zataone.services.api_key_service import APIKeyService
from zataone.storage.database import get_session_factory

router = APIRouter(prefix="/admin", tags=["admin"])

_svc = APIKeyService()


def _check_admin(x_admin_secret: str | None) -> None:
    """Raise 401/503 if admin secret is missing or wrong."""
    secret = os.environ.get("ZATAONE_ADMIN_SECRET", "").strip()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin endpoints are disabled (ZATAONE_ADMIN_SECRET not configured).",
        )
    if x_admin_secret != secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin secret.",
        )


# ---------------------------------------------------------------------------
# Tenant management
# ---------------------------------------------------------------------------


class TenantCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


@router.post("/tenants", status_code=201)
def create_tenant(
    body: TenantCreateRequest,
    x_admin_secret: str | None = Header(None, alias="X-Admin-Secret"),
) -> dict[str, Any]:
    """Create a new tenant. Returns tenant_id to use when creating API keys."""
    _check_admin(x_admin_secret)
    session = get_session_factory()()
    try:
        tenant = Tenant(name=body.name)
        session.add(tenant)
        session.commit()
        return {"tenant_id": str(tenant.id), "name": tenant.name}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        session.close()


@router.get("/tenants")
def list_tenants(
    x_admin_secret: str | None = Header(None, alias="X-Admin-Secret"),
) -> list[dict[str, Any]]:
    """List all tenants."""
    _check_admin(x_admin_secret)
    session = get_session_factory()()
    try:
        tenants = session.query(Tenant).order_by(Tenant.created_at.desc()).all()
        return [
            {
                "tenant_id": str(t.id),
                "name": t.name,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in tenants
        ]
    finally:
        session.close()


# ---------------------------------------------------------------------------
# API key management
# ---------------------------------------------------------------------------


class APIKeyCreateRequest(BaseModel):
    tenant_id: str = Field(..., description="UUID of the tenant this key belongs to")
    name: str = Field(..., min_length=1, max_length=255, description="Human-readable label")
    expires_at: datetime | None = Field(None, description="Optional expiry (ISO 8601)")


@router.post("/api-keys", status_code=201)
def create_api_key(
    body: APIKeyCreateRequest,
    x_admin_secret: str | None = Header(None, alias="X-Admin-Secret"),
) -> dict[str, Any]:
    """
    Create an API key for a tenant.

    Returns the raw key once — store it immediately, it cannot be retrieved again.
    """
    _check_admin(x_admin_secret)
    try:
        tenant_uuid = uuid.UUID(body.tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tenant_id UUID.")

    session = get_session_factory()()
    try:
        # Verify tenant exists.
        tenant = session.query(Tenant).filter(Tenant.id == tenant_uuid).first()
        if tenant is None:
            raise HTTPException(status_code=404, detail="Tenant not found.")

        raw_key, record = _svc.create_key(
            session, tenant_id=tenant_uuid, name=body.name, expires_at=body.expires_at
        )
        session.commit()
        return {
            "api_key": raw_key,
            "key_id": str(record.id),
            "prefix": record.prefix,
            "name": record.name,
            "tenant_id": str(record.tenant_id),
            "expires_at": record.expires_at.isoformat() if record.expires_at else None,
            "warning": "Store this key now — it will not be shown again.",
        }
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        session.close()


@router.get("/api-keys")
def list_api_keys(
    tenant_id: str,
    x_admin_secret: str | None = Header(None, alias="X-Admin-Secret"),
) -> list[dict[str, Any]]:
    """List API keys for a tenant (hashes never returned)."""
    _check_admin(x_admin_secret)
    try:
        tenant_uuid = uuid.UUID(tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tenant_id UUID.")
    session = get_session_factory()()
    try:
        return _svc.list_keys(session, tenant_uuid)
    finally:
        session.close()


@router.delete("/api-keys/{key_id}", status_code=200)
def revoke_api_key(
    key_id: str,
    x_admin_secret: str | None = Header(None, alias="X-Admin-Secret"),
) -> dict[str, Any]:
    """Revoke an API key by ID."""
    _check_admin(x_admin_secret)
    try:
        kid = uuid.UUID(key_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid key_id UUID.")
    session = get_session_factory()()
    try:
        found = _svc.revoke_key(session, kid)
        if not found:
            raise HTTPException(status_code=404, detail="API key not found.")
        session.commit()
        return {"revoked": True, "key_id": key_id}
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        session.close()
