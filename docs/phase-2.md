# Phase 2 — Point-in-time market data and daily valuation

- Status: Complete for the Phase 2 market-data milestone
- Completed: 10 September 2026
- Experiment state: `prelaunch`
- Calculation version: `phase2-v1`

Phase 2 turns provider responses into versioned, queryable valuation inputs and produces reproducible daily portfolio snapshots. It does not start the experiment, publish licensed raw data, or authorize real-money trading.

## Delivered scope

- A provider-neutral market-data contract and an EODHD adapter for ticker/name/ISIN lookup, historical daily OHLCV, adjusted close, current-year v2 exchange schedules, and explicitly bounded v1 historical schedules.
- Stable asset identity separated from exchange listing and provider identity. A listing can distinguish ISIN, ticker, MIC, EODHD exchange code, EODHD symbol, currency, and timezone.
- PostgreSQL-backed price and FX caches with retrieval timestamps, canonical raw-row payloads, SHA-256 checksums, ingestion-run IDs, append-only corrections, and explicit supersession links.
- Materialized exchange sessions classified as `OPEN`, `CLOSED`, or `EARLY_CLOSE`, including holiday names, close times, timezone, retrieval time, and source checksum.
- Missing-price, missing-calendar, missing-FX, upstream-correction, and implausible-price-change exception records.
- Daily portfolio snapshots with cash, position value, total value, realized/unrealized P&L, return, calculation version, and a SHA-256 fingerprint of every authoritative input.
- Per-position snapshot lineage to the exact listing, price revision, exchange-session revision, and FX revision used.
- A worker CLI for lookup, historical backfill, calendar refresh, and the idempotent daily job.
- A Render Blueprint that schedules the completed prior UTC day at `05:30 UTC`, after the provider's documented EOD publication window.
- Deterministic provider, repository, worker, holiday, missing-data, FX, correction, snapshot, and API tests. CI never calls a live market-data API.

## Data and valuation contract

Raw close is the authoritative market value. Adjusted close is retained for reconciliation and later total-return analytics; it is not substituted into a holding's cash value. Price, FX, calendar, and snapshot records are append-only in PostgreSQL. A changed upstream row creates revision `n + 1` linked through `supersedes_id`; the former row remains available.

The reporting FX rate means EUR received for one unit of listing currency. EODHD's `EURUSD.FOREX` close is USD per EUR, so the adapter stores both that raw close and its explicit inverse as EUR per USD. EUR listings use a synthetic calculation rate of one and do not create an unnecessary FX observation.

For valuation date `d`:

```text
position value = quantity × raw close × FX-to-EUR rate
portfolio value = cash + sum(position values)
total return    = portfolio value / starting capital - 1
```

Calculated money uses Phase 1's round-half-even cent boundary. Portfolio state is replayed from immutable transactions whose execution timestamps are no later than `23:59:59.999999 UTC` on the valuation date, so a later trade cannot alter an earlier snapshot. A snapshot's input fingerprint covers calculation/policy version, base currency, starting capital, transaction IDs through that cutoff, derived cash, position quantities/cost bases, and exact price/calendar/FX record IDs. Repeating the same job with the same inputs returns the existing snapshot. Corrected inputs create a new snapshot revision instead of rewriting history.

## Missing-data and holiday rules

The system never treats all absent rows alike:

| Condition | Behavior |
| --- | --- |
| Stored `OPEN` or `EARLY_CLOSE` session has no same-date price | Open `MISSING_EXPECTED_PRICE`; freeze valuation |
| Stored `CLOSED` session has no price | Carry the latest prior close; label `STALE_CLOSED_SESSION`, original date, and stale-day count |
| Exchange calendar does not cover the requested date | Open/fail with `MISSING_CALENDAR`; do not infer a holiday |
| Non-EUR weekday has no same-date FX close | Open/fail with `MISSING_FX_RATE`; freeze valuation |
| Weekend has no FX row | Carry the latest prior FX close; retain its observation ID |
| Provider payload changes | Append a price revision and open `PRICE_CORRECTION` |
| Absolute raw close-to-close move is at least 35% | Open `IMPLAUSIBLE_PRICE_CHANGE` for split/symbol/provider reconciliation |

The EODHD exchange response is checked against the requested year. If the provider returns a different year's holiday set, ingestion fails rather than manufacturing a historical calendar from weekdays.

## HTTP surface

Phase 2 adds read-oriented endpoints; ingestion remains an operator/worker responsibility.

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/market-data/search?q=...` | Normalize EODHD ticker/name/ISIN matches |
| `GET` | `/api/v1/listings/{id}/prices?date_from=...&date_to=...` | Read current price revisions from the database cache |
| `GET` | `/api/v1/market-data/issues?issue_status=OPEN` | Inspect the market-data exception queue |
| `GET` | `/api/v1/portfolios/{id}/snapshots` | Read current daily snapshot revisions and position-level freshness |

Search requires `AIL_EODHD_API_TOKEN`; cached prices and snapshots remain readable during a provider outage.

## Worker commands

Apply migrations and set credentials first:

```bash
cp .env.example .env
docker compose up -d postgres
alembic upgrade head
export AIL_EODHD_API_TOKEN='...'
```

Look up the benchmark by ISIN:

```bash
python -m ai_investment_lab.worker search IE00B4L5Y983 --exchange AS --type etf
```

When creating an asset, persist the selected result's provider symbol and exchange code. The asset response returns the generated `listing_id`. Backfill a date range with an operator-supplied execution key:

```bash
python -m ai_investment_lab.worker prices LISTING_UUID \
  --from 2026-01-01 \
  --to 2026-09-09 \
  --execution-key initial-2026-backfill
```

Run or retry one completed UTC date:

```bash
python -m ai_investment_lab.worker daily --date 2026-09-09
```

Omitting `--date` targets the previous UTC date. Stable job keys make an accidental retry a database-cache hit. Failed or incomplete jobs remain retryable with the same key; a `RUNNING` lease blocks concurrent work and is recoverable after six hours if a process dies. Use a new explicit execution key plus `--refresh` only when intentionally checking price history for provider corrections. After a correction is verified, intentionally rebuild the affected daily valuation with a new key:

```bash
python -m ai_investment_lab.worker daily \
  --date 2026-09-09 \
  --execution-key verified-correction-2026-09-09-1
```

The changed observation IDs alter the input fingerprint and append a snapshot revision. Reusing the normal date-derived key remains a no-op.

## Scheduling and operations

[`render.yaml`](../render.yaml) defines the API and a Docker-based cron job at `30 5 * * *`; Render schedules in UTC. The command migrates the database and runs the prior-day job from the same immutable image as the API. Both `AIL_DATABASE_URL` and `AIL_EODHD_API_TOKEN` are secret, operator-supplied environment values.

The daily run refreshes each active primary listing's calendar and requested EOD row, ingests required non-EUR FX pairs, and then snapshots every portfolio. A failure is recorded on its ingestion run. The operator inspects `/market-data/issues`, verifies the provider/exchange or an issuer notice, and resolves rather than silently substituting another source.

## Verification

Run the local gates:

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy apps/api/src apps/worker/src packages/data_providers/src packages/db/src packages/domain/src
.venv/bin/pytest
npm run lint:web
npm run typecheck:web
npm run build:web
```

CI additionally upgrades PostgreSQL from base to head, checks model/migration parity, downgrades to base, and upgrades again. Live EODHD calls are intentionally excluded; an opt-in credentialed smoke test should be run in staging before Day Zero.

## Pre-Day-Zero boundaries

- EODHD entitlement and the intended public-display rights must be confirmed for `IWDA.AS` and every selected listing. Credentials and licensed raw datasets never enter Git.
- Historical exchange-calendar coverage must be verified for every backfill year; a year mismatch is a hard failure.
- Corporate-action retrieval and split/dividend booking remain a separate acceptance gate before any security affected by an action can be valued through Day Zero. Raw and adjusted closes are stored specifically so that work can be reconciled without double counting.
- The Phase 1 caller-supplied trade reference price is still a verification interface. Automated execution from a sealed decision and an eligible stored next-session open belongs with the decision/execution workflow.
- Trade history is replayed to support a missed or restated historical valuation without using today's mutable position projection. The same guarantee cannot include future corporate actions until their append-only ledger is implemented.

These boundaries do not weaken the Phase 2 milestone: daily market observations and portfolio values are reproducible, stale inputs are visible, corrections are append-only, and missing expected data stops rather than contaminates performance. They do remain blockers to changing the experiment state from `prelaunch` to `active`.
