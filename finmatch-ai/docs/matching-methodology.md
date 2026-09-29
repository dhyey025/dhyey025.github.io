# Matching Methodology

**Scoring version:** `1.0.0`
**Implementation:** [`app/services/matching_engine.py`](../app/services/matching_engine.py)
**Tests:** [`tests/test_matching_engine.py`](../tests/test_matching_engine.py)

This document specifies exactly how FinMatch AI scores and ranks investor mandates
against an issuer. The methodology is **fully deterministic**: pure Python functions,
no randomness, no external calls and **no LLM involvement**. The same inputs always
produce the same scores, ordering and explanation text.

> Scores are illustrative and computed over synthetic data. They are not investment
> advice and do not represent any real institution's process.

---

## 1. Pipeline

```
IssuerProfile + all InvestorMandates
        │
        ▼
 1. Eligibility (hard filters)   → ineligible mandates are removed, never scored
        │
        ▼
 2. Component scoring (5 pure functions, 0–100 total)
        │
        ▼
 3. Ranking (total desc, investor_id asc)
        │
        ▼
 4. top_n truncation (API layer)
```

## 2. Eligibility rules (hard filters)

A mandate is **excluded before scoring** if any rule fails. Excluded mandates can never
appear in recommendations regardless of how well they would have scored.

| Rule | Condition to remain eligible |
|---|---|
| Active mandate | `mandate.active is True` |
| Minimum revenue | `mandate.min_revenue_m is None` **or** `issuer.revenue_m >= mandate.min_revenue_m` (inclusive) |

`active` is a *required* field on `InvestorMandate`, so a mandate can never become
eligible because the flag was omitted.

`number_of_candidates` in the API response is the count of eligible mandates, before
`top_n` truncation.

## 3. Component scores

| Component | Weight | Full credit | Partial credit | Zero |
|---|---:|---|---|---|
| Sector | **30** | Issuer sector ∈ preferred sectors | — | Otherwise |
| Region | **20** | A mandate region *covers* the issuer region | — | Otherwise |
| Deal size | **20** | `min ≤ deal ≤ max` | **10** — within 20% outside the nearest bound | Otherwise |
| Company stage | **15** | Issuer stage ∈ preferred stages | **7.5** — one lifecycle step away | Two or more steps away |
| Risk | **15** | Issuer risk ≤ tolerance | **5** — one level above tolerance | Two levels above |
| **Total** | **100** | | | |

Each component score is `weight × credit`, rounded to 2 decimal places. The total is
the sum of the components, rounded to 2 decimal places.

### 3.1 Label normalisation (sector and region)

Sector and region are free-text labels compared after normalisation:

1. Case-fold (`"TECHNOLOGY"` → `"technology"`)
2. Treat `-` and `_` as spaces (`"Asia-Pacific"` → `"asia pacific"`)
3. Collapse repeated whitespace and trim

There is **no fuzzy or synonym matching** — `"Tech"` does not match `"Technology"`.
Mapping free text onto a controlled taxonomy is planned for Milestone 2 (LLM-assisted
structured extraction), but the comparison itself will remain deterministic.

### 3.2 Sector (30)

Binary: 30 if the normalised issuer sector equals any normalised preferred sector,
otherwise 0.

### 3.3 Region (20)

Binary: 20 if any mandate region **covers** the issuer region, otherwise 0. A mandate
region covers the issuer region when it is:

1. **the same region** (e.g. `UK` covers `UK`);
2. **the parent region** — `Europe` covers `UK` (the common "Europe incl. UK"
   convention); or
3. **`Global`** — covers every region.

Coverage is one-directional: a `UK` mandate does **not** cover a `Europe` issuer, and
an issuer whose region is `Global` is only covered by a `Global` mandate. When several
mandate regions cover the issuer, the most specific one is cited in the explanation.

### 3.4 Deal size (20)

With `low = min_deal_size_m` and `high = max_deal_size_m`:

| Condition | Score |
|---|---:|
| `low ≤ deal ≤ high` (both bounds inclusive) | 20 |
| `deal < low` and `(low − deal) / low ≤ 0.20` | 10 |
| `deal > high` and `(deal − high) / high ≤ 0.20` | 10 |
| Otherwise | 0 |

The 20% tolerance boundary is inclusive and uses a `1e-9` epsilon so binary
floating-point error cannot flip an exact-boundary case (e.g. `(0.1 − 0.08) / 0.1`
evaluates to `0.20000000000000004`).

Worked boundaries for a 100m–500m mandate:

| Deal | Score | Why |
|---:|---:|---|
| 100 | 20 | inclusive minimum |
| 500 | 20 | inclusive maximum |
| 80 | 10 | exactly 20% below minimum |
| 79.99 | 0 | beyond tolerance |
| 600 | 10 | exactly 20% above maximum |
| 600.01 | 0 | beyond tolerance |

### 3.5 Company stage (15)

Stages are an ordered lifecycle:

```
seed → early → growth → late → mature
```

| Distance from the *closest* preferred stage | Score |
|---|---:|
| 0 (preferred stage) | 15 |
| 1 (adjacent) | 7.5 |
| ≥ 2 | 0 |

Stage values are a controlled vocabulary (case-insensitive on input); unknown stages
are rejected with HTTP 422 because an ordinal distance cannot be computed for them.

### 3.6 Risk (15)

`risk_tolerance` is interpreted as a **ceiling** on acceptable issuer risk, not a
target. An issuer at or below the ceiling is fully compatible; exceeding it is
penalised more heavily than stage adjacency because it is a suitability concern.

| Issuer risk ↓ / Investor tolerance → | low | medium | high |
|---|---:|---:|---:|
| **low** | 15 | 15 | 15 |
| **medium** | 5 | 15 | 15 |
| **high** | 0 | 5 | 15 |

## 4. Ranking

Eligible mandates are sorted by:

1. `total_score` **descending**
2. `investor_id` **ascending** (deterministic tie-break)

Because the tie-break is on a unique key, the ranking is independent of the order in
which mandates are stored or loaded.

## 5. Explanations

Each `MatchResult` contains:

- `matched_criteria` / `partially_matched_criteria` / `unmatched_criteria` — one line
  per component in the form `"<Criterion> (<score>/<weight>): <reason>"`;
- `explanation` — a template-generated paragraph built only from those same component
  results plus the eligibility outcome.

The qualitative label at the start of the explanation is derived from the total:

| Total | Label |
|---|---|
| ≥ 80 | Strong |
| ≥ 60 | Moderate |
| ≥ 40 | Limited |
| < 40 | Weak |

## 6. Worked example

Issuer: Consumer, UK, deal 90m, stage `late`, risk `high`.
Mandate: sectors `[Technology]`, regions `[Europe]`, deal 10m–75m, stages `[growth]`,
tolerance `medium`, no revenue minimum, active.

| Component | Result | Score |
|---|---|---:|
| Sector | Consumer ∉ {Technology} | 0 |
| Region | Europe covers UK | 20 |
| Deal size | 90m is 20% above 75m (at tolerance) | 10 |
| Stage | late is adjacent to growth | 7.5 |
| Risk | high exceeds medium by one level | 5 |
| **Total** | | **42.5** (Limited) |

This exact case is asserted in `tests/test_matching_engine.py::TestCalculateMatchKnownCases::test_mixed_match`.

## 7. Guarantees and invariants

- `0 ≤ total_score ≤ 100` and `total_score == round(sum(components), 2)` — enforced by
  a validator on `MatchResult`, so a violation raises instead of being silently clamped.
  An exhaustive grid test (14,400 combinations) checks the bounds of every component.
- Inactive and revenue-ineligible mandates are filtered before scoring.
- Identical inputs yield byte-identical API responses.

## 8. Role of AI in future milestones

When LLM components are introduced (Milestone 2 onwards), they may *interpret* text
(e.g. extract an `IssuerProfile` from a document) and *narrate* the deterministic
results with cited evidence. They will **not** calculate, adjust or override scores or
eligibility. Any LLM-generated explanation will be verified against the structured
component results produced here, and consequential recommendations will require human
review.

## 9. Known limitations

- Binary sector and region scoring: no notion of related sectors (e.g. fintech spans
  Technology and Financial Services) or partial regional overlap.
- Single currency (USD millions); no FX conversion.
- Weights and partial-credit parameters are expert-chosen constants, not calibrated
  against outcome data.
- Many mandates can tie at the same score; the ID tie-break is deterministic but not
  meaningful as a preference signal.
