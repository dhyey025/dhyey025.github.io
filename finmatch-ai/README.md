# FinMatch AI

**Agentic Financial Intelligence & Matching Platform**

> **FinMatch AI is an independent educational portfolio project using synthetic data.
> It is not affiliated with, endorsed by, or a product of any financial institution.**
> Outputs are illustrative and are not investment advice.

![Python](https://img.shields.io/badge/python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688)
![Status](https://img.shields.io/badge/milestone-M1%20deterministic%20foundation-orange)

---

## Overview

FinMatch AI explores how an **agentic AI architecture** could help connect companies
seeking capital (issuers) with potentially relevant investors, while keeping every
consequential decision **deterministic, explainable, evidence-backed and subject to
human review**.

The project is being built incrementally. **Milestone 1 (current)** delivers the
deterministic foundation that every later AI component will build on: domain models,
a synthetic investor dataset, a transparent rule-based matching engine and a REST API.

> **Milestone 1 contains no AI agents, no LLM calls and no machine learning.** All
> scoring is plain, tested Python.

## Problem Statement

Financial institutions process large volumes of information when matching an issuer's
capital requirement to investor mandates: sector focus, geography, ticket size,
company stage, risk appetite and eligibility thresholds. Doing this manually is slow;
doing it with opaque AI is unacceptable in a regulated setting where every
recommendation must be explainable and auditable.

FinMatch AI demonstrates an architecture where:

1. deterministic code owns **eligibility and scoring**;
2. AI (in later milestones) handles **interpretation, retrieval and narration**;
3. every claim is tied to **evidence**, and
4. a **human approves** recommendations before they are acted on.

## Why Agentic AI?

Matching involves heterogeneous tasks — reading unstructured documents, querying
data sources, applying rules, ranking and explaining — that map naturally onto
specialised agents coordinated by a supervisor. The key design principle is a strict
separation of responsibilities:

| Responsibility | Owner |
|---|---|
| Eligibility rules, numerical scoring, ranking | **Deterministic Python** (this milestone) |
| Extracting structured data from text/documents | LLM agent (planned, M2–M3) |
| Tool orchestration and multi-step workflows | LangGraph supervisor (planned, M4) |
| Evidence-backed explanations | LLM, verified against deterministic results (planned, M7) |
| Final approval | **Human reviewer** (planned, M7) |

An LLM will **never** calculate or modify a score or override an eligibility rule.

## Current Architecture

What exists **today** (Milestone 1):

```
Client
  │  HTTP / JSON
  ▼
FastAPI (app/api)           routing, validation, dependency injection — no business logic
  │
  ├── InvestorService       list / look up mandates
  └── MatchingService       load mandates → run engine → apply top_n
          │
          ▼
  Matching Engine           pure functions: eligibility, 5 component scores,
  (app/services/            ranking, template explanations — no I/O, no LLM
   matching_engine.py)
          │
          ▼
InvestorRepository          read-only, validated, in-memory (loaded from JSON at startup)
          │
          ▼
data/investor_mandates.json (synthetic)
```

<details>
<summary><b>Target architecture (planned — not implemented)</b></summary>

```
User → FastAPI → LangGraph Supervisor
                   ├── Mandate Agent
                   ├── Research Agent
                   └── Document Agent
                          ↓
                   Matching Engine  (deterministic — this milestone)
                          ↓
                   Matching Agent → Verification Agent → Risk/Policy Gate
                          ↓
                   Human Review → Explainable Ranked Matches
```

Planned infrastructure: PostgreSQL, pgvector, RAG, MCP, evaluation, observability,
GitHub Actions and cloud deployment.

</details>

### Project structure

```
finmatch-ai/
├── app/
│   ├── main.py                    # app factory, lifespan (data loading), error handlers
│   ├── api/
│   │   ├── dependencies.py        # DI: app.state → repository → services
│   │   └── routes/                # root, health, investors, matches
│   ├── core/                      # config (pydantic-settings), logging, exceptions
│   ├── models/                    # Pydantic v2 domain models
│   ├── repositories/              # investor_repository.py (JSON-backed, read-only)
│   └── services/
│       ├── matching_engine.py     # pure deterministic scoring (framework-free)
│       ├── matching_service.py    # orchestration
│       └── investor_service.py
├── data/investor_mandates.json    # 20 fictional mandates
├── docs/matching-methodology.md   # full scoring specification
├── tests/                         # pytest + pytest-asyncio + httpx
├── Dockerfile  docker-compose.yml  pyproject.toml  .env.example
```

The matching engine is deliberately separated from the service layer: it has no web,
database or I/O dependencies, so it can later be exposed to an agent as a tool (M5/M6)
without giving that agent any way to change how scores are computed.

## Current Capabilities

**Implemented (Milestone 1):**

- ✅ Pydantic v2 domain models with strict validation (`IssuerProfile`,
  `InvestorMandate`, `MatchResult`)
- ✅ 20 synthetic investor mandates across 7 investor types, 7 sectors, 5 regions,
  all company stages and risk tolerances (2 inactive)
- ✅ Deterministic 100-point matching engine with per-component scores
- ✅ Eligibility filters (inactive mandates, minimum revenue)
- ✅ Matched / partially matched / unmatched criteria and template explanations
- ✅ REST API with OpenAPI docs at `/docs`
- ✅ 193 tests, including an exhaustive 14,400-case score-bounds grid
- ✅ Ruff lint/format and mypy `--strict` clean
- ✅ Multi-stage Docker image running as a non-root user with a health check

**Not yet implemented:** LLMs, agents, LangGraph, RAG, vector search, MCP, databases,
authentication, frontend, CI/CD, cloud deployment. See the [roadmap](#project-roadmap).

## Matching Methodology

Full specification: **[docs/matching-methodology.md](docs/matching-methodology.md)**.

**Step 1 — Eligibility (hard filters).** Excluded mandates are never scored or returned:
inactive mandates, and mandates whose `min_revenue_m` exceeds the issuer's revenue.

**Step 2 — Scoring (100 points).**

| Component | Weight | Full | Partial | Zero |
|---|---:|---|---|---|
| Sector | 30 | preferred sector | — | otherwise |
| Region | 20 | covered (exact, `Europe`⊃`UK`, or `Global`) | — | otherwise |
| Deal size | 20 | within `[min, max]` inclusive | 10 if ≤ 20% outside | otherwise |
| Company stage | 15 | preferred stage | 7.5 if adjacent (`seed→early→growth→late→mature`) | otherwise |
| Risk | 15 | issuer risk ≤ tolerance | 5 if one level above | two levels above |

**Step 3 — Ranking.** Total score descending, then `investor_id` ascending.

Sector and region matching is case-insensitive and treats `-`, `_` and spaces as
equivalent (`asia pacific` = `Asia-Pacific`). All monetary values are USD millions.

## Technology Stack

| Area | Technology |
|---|---|
| Language | Python 3.12 |
| API | FastAPI, Uvicorn |
| Validation & settings | Pydantic v2, pydantic-settings |
| Testing | pytest, pytest-asyncio, httpx |
| Quality | Ruff (lint + format), mypy (strict) |
| Packaging | Docker (python:3.12-slim), Docker Compose |

## Getting Started

**Prerequisites:** Python 3.12+.

```bash
cd finmatch-ai
python3.12 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env                 # optional; defaults work out of the box

uvicorn app.main:app --reload
```

Then open:

- API docs (Swagger UI): <http://localhost:8000/docs>
- Health: <http://localhost:8000/api/v1/health>

Run commands from the `finmatch-ai/` directory — the default data path
(`data/investor_mandates.json`) is relative to it. Override with
`FINMATCH_INVESTOR_DATA_PATH`.

### Configuration

| Variable | Default | Purpose |
|---|---|---|
| `FINMATCH_ENVIRONMENT` | `development` | `development` / `test` / `production` |
| `FINMATCH_LOG_LEVEL` | `INFO` | Application log level |
| `FINMATCH_INVESTOR_DATA_PATH` | `data/investor_mandates.json` | Mandate dataset |

No secrets are required for Milestone 1.

## API Examples

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Application information |
| `GET` | `/api/v1/health` | Health check |
| `GET` | `/api/v1/investors?active=true` | List mandates (optional `active` filter) |
| `GET` | `/api/v1/investors/{investor_id}` | One mandate (404 if unknown) |
| `POST` | `/api/v1/matches?top_n=5` | Ranked matches for an issuer (`top_n` 1–50, default 10) |

**Health**

```bash
curl http://localhost:8000/api/v1/health
# {"status":"healthy","service":"finmatch-api"}
```

**Look up an investor**

```bash
curl http://localhost:8000/api/v1/investors/INV-003
```

**Rank investors for an issuer**

```bash
curl -X POST "http://localhost:8000/api/v1/matches?top_n=3" \
  -H "Content-Type: application/json" \
  -d '{
        "id": "ISS-001",
        "company_name": "Lumenfield Analytics Ltd",
        "sector": "Technology",
        "region": "UK",
        "deal_size_m": 50,
        "revenue_m": 150,
        "company_stage": "growth",
        "risk_level": "high"
      }'
```

Abbreviated response:

```json
{
  "issuer": { "id": "ISS-001", "company_name": "Lumenfield Analytics Ltd", "...": "..." },
  "scoring_version": "1.0.0",
  "number_of_candidates": 16,
  "matches": [
    {
      "investor_id": "INV-002",
      "investor_name": "Kestrelmere Growth Partners",
      "investor_type": "Growth Equity Fund",
      "total_score": 100.0,
      "sector_score": 30.0,
      "region_score": 20.0,
      "deal_size_score": 20.0,
      "stage_score": 15.0,
      "risk_score": 15.0,
      "matched_criteria": [
        "Sector (30/30): 'Technology' is a preferred sector",
        "Region (20/20): 'UK' is covered by the 'Europe' mandate region",
        "Deal size (20/20): 50m is within the 20m to 150m range",
        "Company stage (15/15): 'growth' is a preferred stage",
        "Risk (15/15): issuer risk 'high' is within the 'high' risk tolerance"
      ],
      "partially_matched_criteria": [],
      "unmatched_criteria": [],
      "explanation": "Strong match for Kestrelmere Growth Partners with a score of 100/100. Aligned on sector (...), region (...), deal size (...), company stage (...) and risk (...). Eligibility: mandate is active and issuer revenue 150m meets the 10m minimum."
    }
  ]
}
```

Invalid input returns **HTTP 422** with field-level details (e.g. empty company name,
negative deal size, unknown risk level, `top_n=0`). Unknown investor IDs return
**HTTP 404**.

## Testing

```bash
pytest                 # full suite
ruff check .           # lint
ruff format --check .  # formatting
mypy                   # strict type checking
```

Coverage highlights:

- every scoring function, including exact deal-size and tolerance boundaries (with a
  floating-point edge case) and the full 3×3 risk matrix;
- `Global` and `Europe ⊃ UK` region behaviour, and case normalisation;
- eligibility: inactive mandates (including an inactive *perfect* match) and revenue
  thresholds;
- ranking order, tie-breaks, `top_n` behaviour and validation;
- known cases with every component explicitly asserted (100, 90, 42.5 and 0 points);
- an exhaustive grid of 14,400 combinations asserting `0 ≤ score ≤ 100`;
- reproducibility: repeated calls and shuffled inputs give identical output;
- invalid payloads (empty names/sectors, negative/zero/NaN values, bad enums, unknown
  fields, malformed JSON);
- dataset integrity (≥ 15 mandates, unique IDs, full coverage of types/sectors/regions).

## Docker

```bash
cd finmatch-ai
docker compose up --build            # http://localhost:8000/docs
```

Or without Compose:

```bash
docker build -t finmatch-ai .
docker run --rm -p 8000:8000 finmatch-ai
```

The image:

- uses a multi-stage build on `python:3.12-slim` (no build tooling in the runtime image);
- runs as a dedicated **non-root** user (`finmatch`, UID 10001);
- bakes in **no secrets** (`.env` is excluded via `.dockerignore`);
- exposes port **8000** and defines a `HEALTHCHECK` against `/api/v1/health`.

Compose additionally runs the container with a read-only root filesystem and
`no-new-privileges`.

## Project Roadmap

| Milestone | Scope | Status |
|---|---|---|
| **M1** | Deterministic matching foundation — models, synthetic data, rule-based engine, REST API, tests, Docker | ✅ **Current** |
| M2 | LLM integration + structured extraction (issuer profiles from free text, schema-validated) | Planned |
| M3 | Financial-document RAG (chunking, embeddings, retrieval with provenance) | Planned |
| M4 | LangGraph orchestration (supervisor + specialised agents) | Planned |
| M5 | Agent tools + financial data APIs (engine exposed as a tool) | Planned |
| M6 | MCP integration | Planned |
| M7 | Verification + guardrails + human-in-the-loop approval | Planned |
| M8 | Evaluation + observability (audit trail, tracing, offline evals) | Planned |
| M9 | Frontend | Planned |
| M10 | Cloud deployment + CI/CD improvements | Planned |

## Responsible AI / Limitations

- **Illustrative scores.** Weights and partial-credit rules are transparent expert
  choices, not calibrated against real outcomes.
- **Synthetic data only.** All investors, mandates and issuers are fictional. No real
  client, investor or proprietary data is used.
- **Not investment advice.** Outputs must not be used to make financial decisions.
- **Deterministic rules come first.** Future LLM output must never override
  deterministic eligibility rules or modify scores; LLMs may only interpret inputs
  and narrate results.
- **Human in the loop.** Human review will remain a required step in any
  consequential workflow; a recommendation is not "approved" until a person approves it.
- **Grounded claims.** Future AI-generated claims must be traceable to evidence
  (source documents, data records or deterministic score components) and verified
  before display.
- **Current technical limitations:** binary sector/region matching with no synonym
  handling, single currency (USD), no authentication, in-memory read-only data store.

## Disclaimer

FinMatch AI is an independent educational portfolio project using synthetic data. It
is not affiliated with, endorsed by, or a product of any financial institution. All
investor names and mandates are fictional; any resemblance to real organisations is
coincidental. Nothing in this project constitutes investment, legal or financial advice.
