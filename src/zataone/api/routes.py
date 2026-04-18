# zataone API routes

import asyncio
import os
import uuid
from types import SimpleNamespace
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, File, Header, HTTPException, Path, UploadFile
from pydantic import BaseModel, Field

from zataone.core.pipeline import CompliancePipeline
from zataone.models import (
    Asset as AssetModel,
    Evidence as EvidenceModel,
    Signal as SignalModel,
    Verdict as VerdictModel,
    Violation as ViolationModel,
)
from zataone.services.ingestion_service import IngestionService
from zataone.storage.database import get_session_factory

router = APIRouter()


def _use_sync_pipeline() -> bool:
    """
    Run the compliance pipeline in the POST request (not BackgroundTasks).

    Cloud Run throttles CPU after the response unless configured otherwise, so
    background tasks often never finish. Cloud Run sets K_SERVICE; we default to
    sync there. Override with ZATAONE_ASYNC_PIPELINE=true or ZATAONE_SYNC_PIPELINE=false.
    """
    if os.environ.get("ZATAONE_ASYNC_PIPELINE", "").lower() in ("1", "true", "yes"):
        return False
    if os.environ.get("ZATAONE_SYNC_PIPELINE", "").lower() in ("0", "false", "no"):
        return False
    if os.environ.get("ZATAONE_SYNC_PIPELINE", "").lower() in ("1", "true", "yes"):
        return True
    return bool(os.environ.get("K_SERVICE"))


def _asset_status_dict(session: Any, asset_id: uuid.UUID) -> dict[str, Any] | None:
    """Build GET /assets/{id} payload, or None if asset missing."""
    asset = session.query(AssetModel).filter(AssetModel.id == asset_id).first()
    if asset is None:
        return None

    if asset.status == "processing":
        return {"status": "processing", "asset_id": str(asset_id)}

    if asset.status == "failed":
        return {
            "status": "failed",
            "asset_id": str(asset_id),
            "detail": "Compliance pipeline did not complete; see Cloud Run logs.",
        }

    verdict = (
        session.query(VerdictModel)
        .filter(VerdictModel.asset_id == asset_id)
        .order_by(VerdictModel.created_at.desc())
        .first()
    )
    if verdict is None:
        return {"status": asset.status, "asset_id": str(asset_id)}

    result = dict(verdict.result)
    verdict_formatted = _format_verdict_response(result)
    compliance_status = verdict_formatted.pop("status", "")
    return {
        "status": "completed",
        "asset_id": str(asset_id),
        "compliance_status": compliance_status,
        **verdict_formatted,
    }


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class AssetCreateRequest(BaseModel):
    """Request body for POST /assets."""

    content: str = Field(..., description="Asset content (text or base64 for binary)")
    type: Literal["text", "image", "video", "audio"] = Field(
        ..., description="Asset type"
    )
    asset_id: str | None = Field(None, description="Optional asset identifier")
    metadata: dict[str, Any] | None = Field(None, description="Optional metadata")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


def _format_verdict_response(result: dict[str, Any]) -> dict[str, Any]:
    """Format pipeline verdict as API response."""
    return {
        "verdict": result.get("verdict", ""),
        "risk_score": result.get("risk_score", 0.0),
        "status": result.get("status", ""),
        "violations": result.get("violations", []),
        "signals": result.get("signals", []),
        "fix_suggestions": result.get("fix_suggestions", []),
        "metadata": result.get("metadata", {}),
    }


def _run_pipeline_background(
    asset: Any,
    asset_id: uuid.UUID,
    tenant_id: str | None,
    idempotency_key: str | None,
) -> None:
    """Background task: run pipeline and persist result to existing asset."""
    import logging

    logger = logging.getLogger(__name__)
    try:
        pipeline = CompliancePipeline(domain="ad_compliance")
        pipeline.run(
            asset,
            tenant_id=tenant_id,
            persist=True,
            idempotency_key=idempotency_key,
            existing_asset_id=asset_id,
        )
        logger.info("Background pipeline completed for asset %s", asset_id)
    except Exception as e:
        logger.exception("Background pipeline failed for asset %s: %s", asset_id, e)
        session = get_session_factory()()
        try:
            IngestionService().set_asset_status(session, asset_id, "failed")
        except Exception:
            logger.exception("Could not mark asset %s as failed", asset_id)
        finally:
            session.close()


@router.post("/assets")
def post_assets(
    background_tasks: BackgroundTasks,
    body: AssetCreateRequest,
    x_tenant_id: str | None = Header(None, alias="X-Tenant-ID"),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    """
    Run compliance check on an asset (async).

    Returns immediately with status: processing and asset_id.
    Poll GET /assets/{asset_id} for the verdict when ready.

    Optional Idempotency-Key: if provided and an asset with the same key exists,
    returns the existing verdict without re-running the pipeline.
    """
    if idempotency_key:
        session = get_session_factory()()
        try:
            ingestion = IngestionService()
            existing = ingestion.find_existing_verdict(
                session, idempotency_key, tenant_id=x_tenant_id
            )
            if existing:
                eid, eresult = existing
                out = _format_verdict_response(eresult)
                out["asset_id"] = str(eid)
                return out
        finally:
            session.close()

    asset = SimpleNamespace(
        asset_id=body.asset_id,
        content=body.content,
        type=body.type,
        metadata=body.metadata or {},
    )

    asset_id = uuid.uuid4()
    session = get_session_factory()()
    try:
        ingestion = IngestionService()
        ingestion.create_asset_stub(
            session,
            asset,
            asset_id=asset_id,
            tenant_id=x_tenant_id,
            idempotency_key=idempotency_key,
        )
        session.commit()
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        session.close()

    if _use_sync_pipeline():
        try:
            CompliancePipeline(domain="ad_compliance").run(
                asset,
                tenant_id=x_tenant_id,
                persist=True,
                idempotency_key=idempotency_key,
                existing_asset_id=asset_id,
            )
        except Exception as e:
            session = get_session_factory()()
            try:
                IngestionService().set_asset_status(session, asset_id, "failed")
            finally:
                session.close()
            raise HTTPException(status_code=500, detail=str(e)) from e
        session = get_session_factory()()
        try:
            out = _asset_status_dict(session, asset_id)
            if out is None:
                raise HTTPException(status_code=404, detail="Asset not found")
            return out
        finally:
            session.close()

    background_tasks.add_task(
        _run_pipeline_background,
        asset,
        asset_id,
        x_tenant_id,
        idempotency_key,
    )

    return {"status": "processing", "asset_id": str(asset_id)}


@router.post("/assets/image")
async def post_assets_image(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    x_tenant_id: str | None = Header(None, alias="X-Tenant-ID"),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    """
    Run compliance check on an uploaded image (async).

    Returns immediately with status: processing and asset_id.
    Poll GET /assets/{asset_id} for the verdict when ready.

    Optional Idempotency-Key: if provided and an asset with the same key exists,
    returns the existing verdict without re-running the pipeline.
    """
    if idempotency_key:
        session = get_session_factory()()
        try:
            ingestion = IngestionService()
            existing = ingestion.find_existing_verdict(
                session, idempotency_key, tenant_id=x_tenant_id
            )
            if existing:
                eid, eresult = existing
                out = _format_verdict_response(eresult)
                out["asset_id"] = str(eid)
                return out
        finally:
            session.close()

    try:
        image_bytes = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {e}") from e

    asset = SimpleNamespace(
        asset_id=None,
        content=None,
        image_data=image_bytes,
        type="image",
    )

    asset_id = uuid.uuid4()
    session = get_session_factory()()
    try:
        ingestion = IngestionService()
        ingestion.create_asset_stub(
            session,
            asset,
            asset_id=asset_id,
            tenant_id=x_tenant_id,
            idempotency_key=idempotency_key,
        )
        session.commit()
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        session.close()

    if _use_sync_pipeline():

        def _run_img_pipeline() -> None:
            CompliancePipeline(domain="ad_compliance").run(
                asset,
                tenant_id=x_tenant_id,
                persist=True,
                idempotency_key=idempotency_key,
                existing_asset_id=asset_id,
            )

        try:
            await asyncio.to_thread(_run_img_pipeline)
        except Exception as e:
            session = get_session_factory()()
            try:
                IngestionService().set_asset_status(session, asset_id, "failed")
            finally:
                session.close()
            raise HTTPException(status_code=500, detail=str(e)) from e
        session = get_session_factory()()
        try:
            out = _asset_status_dict(session, asset_id)
            if out is None:
                raise HTTPException(status_code=404, detail="Asset not found")
            return out
        finally:
            session.close()

    background_tasks.add_task(
        _run_pipeline_background,
        asset,
        asset_id,
        x_tenant_id,
        idempotency_key,
    )

    return {"status": "processing", "asset_id": str(asset_id)}


@router.get("/assets/{asset_id}")
def get_asset(
    asset_id: uuid.UUID = Path(..., description="Asset ID from POST response"),
) -> dict[str, Any]:
    """
    Get asset status and verdict.

    Returns status: processing while the compliance check runs, or status: completed
    with verdict, risk_score, violations, etc. when done.
    """
    session = get_session_factory()()
    try:
        out = _asset_status_dict(session, asset_id)
        if out is None:
            raise HTTPException(status_code=404, detail="Asset not found")
        return out
    finally:
        session.close()


def _model_to_dict(obj: Any, exclude: set[str] | None = None) -> dict[str, Any]:
    """Convert SQLAlchemy model to JSON-serializable dict."""
    if obj is None:
        return {}
    exclude = exclude or set()
    d = {}
    for c in obj.__table__.columns:
        if c.name in exclude:
            continue
        val = getattr(obj, c.name)
        if hasattr(val, "hex"):
            d[c.name] = str(val)
        elif hasattr(val, "isoformat"):
            d[c.name] = val.isoformat()
        else:
            d[c.name] = val
    return d


@router.get("/assets/{asset_id}/graph")
def get_asset_graph(
    asset_id: uuid.UUID = Path(..., description="Asset ID"),
) -> dict[str, Any]:
    """
    Get full evidence graph for an asset.

    Returns asset, signals, violations, evidence, verdict.
    """
    session = get_session_factory()()
    try:
        asset = session.query(AssetModel).filter(AssetModel.id == asset_id).first()
        if asset is None:
            raise HTTPException(status_code=404, detail="Asset not found")

        signals = session.query(SignalModel).filter(SignalModel.asset_id == asset_id).all()
        violations = (
            session.query(ViolationModel).filter(ViolationModel.asset_id == asset_id).all()
        )
        evidence = session.query(EvidenceModel).filter(EvidenceModel.asset_id == asset_id).all()
        verdict = (
            session.query(VerdictModel)
            .filter(VerdictModel.asset_id == asset_id)
            .order_by(VerdictModel.created_at.desc())
            .first()
        )

        return {
            "asset": _model_to_dict(asset),
            "signals": [_model_to_dict(s) for s in signals],
            "violations": [_model_to_dict(v) for v in violations],
            "evidence": [_model_to_dict(e) for e in evidence],
            "verdict": _model_to_dict(verdict) if verdict else {},
        }
    finally:
        session.close()
