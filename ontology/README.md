# ZataOne Canonical Compliance Ontology

One unified corpus where every **platform** (Meta, Google, TikTok, …) and
**regulator** (FTC, FDA, …) policy maps into the **same underlying ontology**.
This is the foundation for ZataOne's moat: structured corpus + cross-source
mappings + a labeled evaluation dataset with measured precision/recall.

## Files

| File | Purpose |
|------|---------|
| `schema.yaml` | **Canonical schema v0** — entities, fields, allowed values, graph |
| `categories.yaml` | Universal advertising-risk categories (the foundation axis) |
| `corpus/meta_ads_us.yaml` | Meta Ads (US) — Misleading + Health + Financial clauses + rules |
| `corpus/google_ads_us.yaml` | Google Ads (US) — Misrepresentation + Healthcare/Medicines + Financial clauses + rules |
| `corpus/tiktok_ads_us.yaml` | TikTok Ads (US) — Misleading & false content + Healthcare/Pharmaceuticals + Financial |
| `corpus/linkedin_ads_us.yaml` | LinkedIn Ads (US) — Financial services clauses + rules |
| `corpus/regulators_us.yaml` | FTC + FDA + SEC + FINRA + CFPB (US) clauses + rules (Misleading + Health + Financial) |
| `mappings.yaml` | Cross-source links: equivalent clauses → one `canonical_id` |
| `examples/eval_seed.yaml` | Labeled evaluation dataset (150 examples: 30 misleading + 60 health + 60 financial) |
| `corpus_version.yaml` | Frozen, versioned corpus releases (Ad Corpus v0.1, v0.2, v0.3, …) |
| `validate.py` | Validator: parse + referential integrity + evidence/applicability completeness |

## Entities

```
category ─< clause >── source
   │           │
   └─< rule >──┘   (rule.canonical_id unifies equivalent rules across sources)
        │
   mapping (clause ↔ clause, same category/canonical_id)
        │
   example >── clause   (eval dataset; label + violated_clause_ids)
```

## Schema highlights (v0)

- **`canonical_id` on rules** — equivalent platform/regulator rules share one universal rule.
- **`priority`** — resolves conflicts when multiple clauses apply (regulator usually outranks platform).
- **`modality`** on clauses/rules — `text · image · video · audio · landing_page`.
- **`status`** (`active · deprecated · superseded`) + **`superseded_by`** — policies change; history is auditable.
- **`last_verified_at`** on sources/clauses — "when did we last confirm this is current?".
- **`confidence`** on mappings (`exact · high · medium`) — not every mapping is perfectly equivalent.
- **`evidence`** on every clause (`quote · source_url · section · retrieved_at`) — full legal/audit trail.
- **`last_reviewed_by`** (`human · ai`) — `ai` until a person manually verifies the clause on the live page.
- **`applicability`** (optional: `countries · audience · industries`) — powers scoped retrieval later (e.g. "US health ad for 18+"). `audience` ∈ `all · 18+ · 21+ · 25+`; `industries` are category ids (`[all]` = cross-industry).

> Schema is **FROZEN** at v1.0.0. Effort now goes into expanding the corpus, the
> eval dataset, and benchmarking — not redesigning the ontology.

## Scope so far

- **Categories:** `misleading` (deep), `health` (deep), `financial` (deep)
- **Sources:** Meta Ads, Google Ads, TikTok Ads, LinkedIn Ads, FTC, FDA, SEC, FINRA, CFPB
- **Jurisdiction:** US
- **Current corpus version:** `Ad Corpus v0.3` (see `corpus_version.yaml`)

### Misleading / Deceptive — canonical rules (vertical 1)

All platform/regulator clauses for this vertical collapse into these `canonical_id`s:

| `canonical_id` | Sources mapped |
|----------------|----------------|
| `misleading.exaggerated_results` | Meta, Google |
| `misleading.guaranteed_outcomes` | Meta, TikTok |
| `misleading.unsubstantiated_objective_claims` | FTC (backbone), TikTok |
| `misleading.missing_or_inconsistent_material_info` | Google, TikTok |
| `misleading.false_affiliation_or_endorsement` | Meta, Google |
| `misleading.clickbait_or_fake_ui` | Google |
| `misleading.before_after_distortion` | Meta, Google, TikTok |

FTC carries higher `priority` than platform rules on conflict.

### Health / Medical — canonical rules (vertical 2)

| `canonical_id` | Sources mapped |
|----------------|----------------|
| `health.disease_cure_treatment_claims` | Meta, Google, FTC, FDA |
| `health.unsubstantiated_health_claims` | FTC, FDA, Google |
| `health.prescription_drug_promotion_restricted` | Google, TikTok |
| `health.unapproved_or_dangerous_products` | Google, TikTok |
| `health.negative_self_perception_body_image` | Meta (only — no cross-source map yet) |
| `health.rx_fair_balance_risk_disclosure` | FDA (only — no cross-source map yet) |
| `health.health_privacy_sensitive_attributes` | Meta (only — no cross-source map yet) |
| `health.material_risk_safety_disclosure` | FTC (only — no cross-source map yet) |

FTC/FDA carry higher `priority` (95) than platform rules on conflict. Single-source
canonicals have no `mapping` entry yet — they get one once a second source matches.

### Financial services & investments — canonical rules (vertical 3)

| `canonical_id` | Sources mapped |
|----------------|----------------|
| `finance.prohibited_predatory_products` | Meta, Google, TikTok, LinkedIn |
| `finance.guaranteed_returns_or_risk_free` | TikTok, LinkedIn, FINRA, FTC |
| `finance.misleading_or_unbalanced_claims` | LinkedIn, FINRA, SEC |
| `finance.performance_claims_substantiation` | FINRA, SEC, FTC |
| `finance.required_cost_and_risk_disclosures` | Google, CFPB, TikTok, Meta |
| `finance.credit_advertising_trigger_terms` | CFPB, Google |
| `finance.licensing_registration_required` | Meta, Google, TikTok, LinkedIn |
| `finance.crypto_restricted` | Meta, Google, TikTok |
| `finance.loan_modification_foreclosure_restricted` | Google, LinkedIn, CFPB |
| `finance.mortgage_advertising_prohibited_acts` | CFPB (only — no cross-source map yet) |
| `finance.testimonials_endorsements_disclosure` | SEC (only — no cross-source map yet) |

SEC / FINRA / FTC / CFPB carry higher `priority` (90–95) than platform rules on
conflict. Two canonicals are intentionally single-source and kept honest until a
second official source genuinely matches.

Financial sources: Meta Ad Standards (Prohibited Financial Products, Cryptocurrency,
Financial & Insurance Services), Google Financial products and services, TikTok
Financial Services (US market section), LinkedIn Advertising Policies (Financial
Services), FTC (Penalty Offenses re money-making opportunities + 16 CFR 437.4), SEC
Marketing Rule (17 CFR 275.206(4)-1), FINRA Rule 2210, CFPB Reg Z / TILA (12 CFR
1026.24). Jurisdiction: US only.

> **TikTok US note:** TikTok's healthcare policy is per-market. In the *United
> States*, prescription/OTC meds, pharmacies, fillers, and microdermabrasion
> *may be allowed* with FDA / NABP / LegitScript certification and 18+ targeting
> (they are not blanket-banned as in some other countries). Clauses here reflect
> the US section only, per the "don't invent" rule.

Health sources: Meta Ad Standards (Health & Wellness, deceptive practices), Google
Healthcare & Medicines, TikTok Healthcare & Pharmaceuticals, FTC Health Products
Compliance Guidance, FDA prescription-drug advertising (21 CFR 202.1, "fair balance").

## Corpus versioning

Each completed category is **frozen** and assigned a version in
`corpus_version.yaml` so the corpus is reproducible and benchmarkable alongside
the eval dataset:

- **Ad Corpus v0.1** — Misleading / Deceptive (frozen)
- **Ad Corpus v0.2** — adds Health / Medical (frozen)
- **Ad Corpus v0.3** — adds Financial services & investments (frozen, current)

## Build order

1. ✅ Canonical schema (this directory).
2. ✅ Misleading / Deceptive vertical → **Ad Corpus v0.1** (30 eval examples).
3. ✅ Health / Medical vertical: Meta + Google + TikTok + FTC + FDA, mapped → **Ad Corpus v0.2** (60 eval examples).
4. ✅ Financial vertical: Meta + Google + TikTok + LinkedIn + FTC + SEC + FINRA + CFPB, mapped → **Ad Corpus v0.3** (60 eval examples).
5. Build the 1,000+ labeled evaluation dataset across the three frozen verticals; measure precision/recall per `category_id` and per `canonical_id`.
6. Deepen each canonical rule (more clauses, edge cases); then add jurisdictions (EU/UK) and platforms (X, Amazon Ads). New domains (housing/employment, gambling, etc.) come after the eval dataset.

> Clause text is sourced from official policy pages (Meta Transparency Center,
> Google Ads Help, TikTok Business Help Center, LinkedIn Advertising Policies,
> FTC.gov, FDA.gov, SEC.gov / 17 CFR 275.206(4)-1, FINRA Rule 2210, CFPB / 12 CFR
> 1026.24, 21 CFR 202.1). Some pages are JS-heavy and were captured via
> official-source search snippets; **verify verbatim text and effective dates
> against the cited URLs before using metrics or decisions externally.** Run
> `python ontology/validate.py` after any change.

## Relationship to the engine policies

The legacy rule-engine format lives at
`src/zataone/domains/ad_compliance/policies/*.yaml` (keyword/pattern matching).
This ontology is the **cross-source canonical layer** above it: the engine packs
are one `source`; regulators are another; `mappings.yaml` unifies them. They are
complementary — the ontology does not replace the engine packs.
