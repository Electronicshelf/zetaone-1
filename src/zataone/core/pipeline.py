# zataone core pipeline

"""
Domain-agnostic compliance pipeline.
Orchestrates extractors, policy evaluation, evidence, verdict, and persistence.
"""

import importlib
import logging
import os
import time
import uuid
from typing import Any

from zataone.extractors.registry import ExtractorRegistry
from zataone.policy_engine.engine import PolicyEngine
from zataone.storage.database import get_session_factory
from zataone.services.audit_service import AuditService
from zataone.services.evidence_service import EvidenceService
from zataone.services.ingestion_service import IngestionService
from zataone.services.signal_service import SignalService
from zataone.services.verdict_service import VerdictService
from zataone.services.violation_service import ViolationService

logger = logging.getLogger(__name__)


def _core_stub_extractors_disabled() -> bool:
    """When true, ad_compliance skips core OCR/Vision/Embedding/VLM (domain extractors only)."""
    v = os.environ.get("ZATAONE_DISABLE_CORE_STUB_EXTRACTORS", "").strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    if v in ("0", "false", "no", "off"):
        return False
    return False


class CompliancePipeline:
    """
    ZataOne core compliance pipeline.
    Loads domain extractors and policies, orchestrates the full flow.
    """

    def __init__(self, domain: str):
        """
        Initialize pipeline for a domain.

        Args:
            domain: Domain name (e.g. "ad_compliance").
                   Loads extractors from zataone.domains.<domain>.extractors
                   and policy pack from zataone.domains.<domain>.policies
        """
        self._domain = domain
        self._extractor_registry = ExtractorRegistry()
        self._policy_engine = PolicyEngine()
        self._evidence_service = EvidenceService()
        self._verdict_service = VerdictService()
        self._ingestion_service = IngestionService()
        self._signal_service = SignalService()
        self._violation_service = ViolationService()
        self._audit_service = AuditService()

        self._load_domain_extractors()
        self._load_domain_policies()

    def _load_domain_extractors(self) -> None:
        """Load and register extractors from domain module."""
        domain_module = importlib.import_module(f"zataone.domains.{self._domain}")
        domain_path = os.path.dirname(domain_module.__file__)
        config = self._load_domain_config(domain_path)

        extractors_module = importlib.import_module(
            f"zataone.domains.{self._domain}.extractors"
        )

        extractor_classes = []
        if hasattr(extractors_module, "OCRExtractor"):
            extractor_classes.append(("OCRExtractor", {}))
        if hasattr(extractors_module, "VisionExtractor"):
            vision_cfg = config.get("vision", {})
            extractor_classes.append(
                ("VisionExtractor", {"object_queries": vision_cfg.get("object_queries")})
            )
        if hasattr(extractors_module, "EmbeddingExtractor"):
            emb_cfg = config.get("embedding", {})
            reg_texts = [
                (k, v) for k, v in emb_cfg.get("regulation_texts", {}).items()
            ]
            extractor_classes.append(
                (
                    "EmbeddingExtractor",
                    {
                        "regulation_texts": reg_texts or None,
                        "similarity_threshold": emb_cfg.get("similarity_threshold", 0.6),
                    },
                )
            )
        if hasattr(extractors_module, "VLMExtractor"):
            extractor_classes.append(("VLMExtractor", {}))

        # Core extractors for ad_compliance (text always; OCR/Vision/Embedding/VLM optional stubs)
        if self._domain == "ad_compliance":
            from zataone.extractors.text_extractor import TextExtractor
            from zataone.extractors.ocr_extractor import OCRExtractor
            from zataone.extractors.vision_extractor import VisionExtractor
            from zataone.extractors.embedding_extractor import EmbeddingExtractor
            from zataone.extractors.vlm_extractor import VLMExtractor

            self._extractor_registry.register(TextExtractor())
            if _core_stub_extractors_disabled():
                logger.info(
                    "Core stub extractors disabled (ZATAONE_DISABLE_CORE_STUB_EXTRACTORS); "
                    "using domain OCR/Vision/Embedding/VLM only."
                )
            else:
                self._extractor_registry.register(OCRExtractor())
                self._extractor_registry.register(VisionExtractor())
                self._extractor_registry.register(EmbeddingExtractor())
                self._extractor_registry.register(VLMExtractor())

        for name, kwargs in extractor_classes:
            cls = getattr(extractors_module, name)
            kwargs_clean = {k: v for k, v in kwargs.items() if v is not None}
            extractor = cls(**kwargs_clean)
            self._extractor_registry.register(extractor)

    def _load_domain_config(self, domain_path: str) -> dict:
        """Load domain config YAML if present."""
        import yaml

        config_path = os.path.join(domain_path, "configs", "meta_ads_config.yaml")
        if not os.path.exists(config_path):
            config_path = os.path.join(domain_path, "configs", f"{self._domain}_config.yaml")
        if not os.path.exists(config_path):
            return {}
        with open(config_path, "r") as f:
            return yaml.safe_load(f) or {}

    def _load_domain_policies(self) -> None:
        """Load policy pack from domain policies."""
        domain_module = importlib.import_module(f"zataone.domains.{self._domain}")
        domain_path = os.path.dirname(domain_module.__file__)

        import yaml

        policy_path = os.path.join(domain_path, "policies", "meta_ads.yaml")
        if not os.path.exists(policy_path):
            policy_path = os.path.join(domain_path, "policies", f"{self._domain}.yaml")
        if not os.path.exists(policy_path):
            return

        with open(policy_path, "r") as f:
            data = yaml.safe_load(f) or {}
        rules = data.get("rules", {})

        vision_support_map = {}
        embedding_rule_map = {}
        try:
            mappings_module = importlib.import_module(
                f"zataone.domains.{self._domain}.mappings"
            )
            vision_support_map = getattr(mappings_module, "VISION_SUPPORT_MAP", {})
            embedding_rule_map = getattr(mappings_module, "EMBEDDING_RULE_MAP", {})
        except ImportError:
            pass

        self._policy_engine.load_policy_pack(
            rules=rules,
            vision_support_map=vision_support_map,
            embedding_rule_map=embedding_rule_map,
        )

    def run(
        self,
        asset: Any,
        tenant_id: uuid.UUID | str | None = None,
        persist: bool = True,
        idempotency_key: str | None = None,
        existing_asset_id: uuid.UUID | None = None,
    ) -> dict:
        """
        Run the compliance pipeline on an asset.

        Args:
            asset: Asset with image_data (and domain-specific fields).
            tenant_id: Optional tenant ID for persistence. If None and persist=True,
                       uses default tenant.
            persist: If True, persist full compliance graph to database.

        Returns:
            Verdict dict with keys: verdict, risk_score, violations, signals,
            status, fix_suggestions, metadata.
        """
        start_time = time.perf_counter()
        signals = []
        counts: dict[str, int] = {}
        for extractor in self._extractor_registry.list():
            eid = getattr(extractor, "extractor_id", None) or type(extractor).__name__
            try:
                extracted = list(extractor.extract(asset) or [])
            except Exception:
                logger.exception("Extractor failed: id=%s", eid)
                counts[eid] = 0
                continue
            n = len(extracted)
            counts[eid] = n
            if n:
                signals.extend(extracted)
                logger.info("Extractor produced signals: id=%s count=%d", eid, n)

        producers = sorted(eid for eid, n in counts.items() if n > 0)
        logger.info(
            "Extraction complete: total_signals=%d counts=%s producers=%s",
            len(signals),
            counts,
            producers,
        )

        violations = self._policy_engine.evaluate(signals)

        evidence = self._evidence_service.generate(signals, violations)

        verdict = self._verdict_service.generate(evidence)

        asset_id_result: uuid.UUID | None = existing_asset_id
        if persist:
            asset_id_result = self._persist_compliance_graph(
                asset=asset,
                signals=signals,
                evidence=evidence,
                verdict=verdict,
                tenant_id=tenant_id,
                idempotency_key=idempotency_key,
                existing_asset_id=existing_asset_id,
            )

        if persist and existing_asset_id is not None and asset_id_result is None:
            sess = get_session_factory()()
            try:
                self._ingestion_service.set_asset_status(sess, existing_asset_id, "failed")
            except Exception:
                logger.exception(
                    "Could not mark asset %s failed after persistence error",
                    existing_asset_id,
                )
            finally:
                sess.close()

        processing_time_ms = round((time.perf_counter() - start_time) * 1000)
        tenant_id_str = str(tenant_id) if tenant_id is not None else None
        logger.info(
            "Pipeline completed",
            extra={
                "asset_id": str(asset_id_result) if asset_id_result else None,
                "tenant_id": tenant_id_str,
                "verdict": verdict.get("verdict", ""),
                "risk_score": verdict.get("risk_score", 0.0),
                "processing_time_ms": processing_time_ms,
            },
        )
        return verdict

    def _persist_compliance_graph(
        self,
        asset: Any,
        signals: list[Any],
        evidence: dict[str, Any],
        verdict: dict[str, Any],
        tenant_id: uuid.UUID | str | None,
        idempotency_key: str | None = None,
        existing_asset_id: uuid.UUID | None = None,
    ) -> uuid.UUID | None:
        """
        Persist full compliance graph. Single shared session, atomic transaction.
        Order: 1) asset 2) signals 3) violations 4) evidence 5) verdict 6) audit event.
        Returns asset_id.
        """
        session = None
        try:
            SessionLocal = get_session_factory()
            session = SessionLocal()

            if existing_asset_id is not None:
                from zataone.models import Asset as AssetModel
                from zataone.services.ingestion_service import compute_content_hash

                asset_record = session.query(AssetModel).filter(
                    AssetModel.id == existing_asset_id
                ).first()
                if asset_record is None:
                    logger.error("Existing asset %s not found", existing_asset_id)
                    return None
                asset_record.status = "completed"
                asset_record.content_hash = compute_content_hash(asset)
                session.flush()
            else:
                asset_record = self._ingestion_service.persist_asset(
                    session, asset, tenant_id, idempotency_key=idempotency_key
                )

            signal_records = self._signal_service.persist_signals(
                session, asset_record.id, signals
            )

            violation_records = self._violation_service.persist_violations(
                session, asset_record.id, signal_records, evidence.get("violations", [])
            )

            self._evidence_service.persist_evidence(
                session, asset_record.id, signal_records, violation_records
            )

            verdict_record = self._verdict_service.persist_verdict(
                session, asset_record.id, verdict
            )

            self._audit_service.persist_audit_event(
                session,
                asset_record.id,
                verdict_record.id,
                "COMPLIANCE_CHECK",
            )

            session.commit()
            return asset_record.id
        except Exception as e:
            if session is not None:
                session.rollback()
            logger.exception("Persistence failed: %s", e)
            return None
        finally:
            if session is not None:
                session.close()
