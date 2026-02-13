# ZetaOne

**Deterministic, evidence-first AI compliance platform for enterprise regulatory enforcement.**

ZetaOne provides a scalable architecture for validating content against configurable policies—from single-domain checks to global multi-modal compliance. AI models act as sensors that extract signals; policies make deterministic, auditable decisions.

---

## Overview

ZetaOne is designed for organizations that need:

- **Legally defensible decisions** — Deterministic evaluation with complete audit trails
- **Evidence-first design** — Every violation links to traceable source content
- **Configuration-driven growth** — Add domains, modalities, and jurisdictions without core rewrites
- **Multi-tenant readiness** — Built for SaaS deployment with tenant isolation

The platform follows a strict separation of concerns: AI extracts signals, the policy engine evaluates rules, and the evidence system produces human-reviewable proof.

---

## Architecture

```
Asset → Normalization → Signal Extraction → Policy Evaluation → Evidence → Verdict → Audit
```

| Layer | Responsibility |
|-------|-----------------|
| **Asset Ingestion** | Multi-protocol intake, format normalization, content chunking |
| **Signal Extraction** | Pluggable extractors (text, image, video) produce machine-readable facts |
| **Policy Engine** | Deterministic rule evaluation against signals |
| **Evidence** | Traceable, immutable proof with anchors to source content |
| **Verdict** | Final decision with risk scoring and explainability |
| **Audit** | Immutable trail for regulatory and operational transparency |

**Core principle:** AI models are sensors—they extract signals but never make enforcement decisions. Policies are configuration-driven and versioned for auditability.

---

## Deterministic Pipeline

1. **Asset** — Content ingested and normalized to an internal representation
2. **Signal** — Extractors produce structured facts (entities, claims, metadata)
3. **Policy** — Rules evaluate signals; same inputs always yield same outputs
4. **Evidence** — Violations generate anchored, tamper-proof evidence bundles
5. **Verdict** — Compliant / non-compliant / needs-review with risk score
6. **Audit** — Every decision recorded for compliance and debugging

Expansion is configuration-only:

- **Policy packs** — New domains (healthcare, finance, advertising) via YAML/config
- **Signal extractors** — New modalities (text, image, video) as pluggable modules
- **Jurisdiction adapters** — New regulations via policy overrides

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| **Backend** | Python 3.11+, FastAPI |
| **Database** | PostgreSQL, SQLAlchemy, Alembic |
| **Config** | YAML, python-dotenv |
| **Logging** | Loguru |
| **Packaging** | setuptools, pyproject.toml (PEP 621) |

---

## Local Development

### Prerequisites

- Python 3.11+
- pip

### Setup

```bash
# Clone the repository
git clone https://github.com/your-org/zetaone.git
cd zetaone

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in editable mode
pip install -e .

# Run the API
uvicorn zetaone.main:app --reload --port 8000
```

### Verify

```bash
curl http://localhost:8000/health
# {"status":"ok","service":"zetaone"}
```

---

## Docker Instructions

### Build and run

```bash
# From project root
docker compose -f docker/docker-compose.yml up --build
```

The API is available at `http://localhost:8000`. Source code is mounted for development; changes are reflected on reload.

### Project name

The Compose project name is `zetaone`. Override if needed:

```bash
docker compose -p zetaone -f docker/docker-compose.yml up
```

---

## Future Roadmap

| Phase | Focus |
|-------|-------|
| **Foundation** | PostgreSQL models, asset ingestion API, basic extractors, policy engine |
| **MVP** | HIPAA policy pack, evidence system, verdict UI, audit log, auth |
| **Scale** | Image/video extractors, multi-tenancy, webhooks, 10+ policy packs |
| **Platform** | Custom extractor SDK, policy builder, marketplace, SOC 2 |
| **Ecosystem** | White-label, platform partnerships, on-prem, advanced ML |

---

## License

See [LICENSE](LICENSE) for details.
