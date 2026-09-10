# AI Investment Lab

> An open, auditable paper-investing experiment testing whether an AI portfolio manager can outperform the market.

AI Investment Lab starts with EUR 10,000 of fictional capital and records every portfolio decision before its outcome is known. The portfolio is compared with a passive MSCI World proxy over an initial 12-month experiment. Returns, risk, costs, decision quality, and the evidence available at decision time are all preserved.

This is an engineering and research project. It is not financial advice, a promise of returns, or a real-money trading system.

## Experiment baseline

| Item | Phase 0 decision |
| --- | --- |
| Base currency | EUR |
| Starting capital | EUR 10,000 |
| Planned start | September 2026; exact Day Zero timestamp is set only when the portfolio engine is ready |
| Initial duration | 12 calendar months |
| Benchmark | iShares Core MSCI World UCITS ETF USD (Acc), EUR listing on Euronext Amsterdam (`IWDA`, ISIN `IE00B4L5Y983`) |
| Market data | EODHD end-of-day prices, corporate actions, instrument metadata, and FX rates |
| Execution | First regular-session open strictly after a decision is sealed |
| Trading costs | max(EUR 1.00, 0.10% of notional), plus 0.05% adverse slippage and 0.20% FX fee when applicable |
| Investment style | Benchmark-aware, long-only quality at a reasonable price (QARP), normally held for 6–24 months |
| Primary result | Net portfolio total return minus net benchmark total return |
| Mandate | Long-only public equities, UCITS ETFs, and cash; no leverage or derivatives |

The exact, machine-readable baseline is in [`config/experiment-policy.json`](config/experiment-policy.json). It remains `prelaunch` until Day Zero. Once launched, changes create a new version rather than rewriting the original.

## Phase 0

- [x] Create GitHub repository
- [x] Add README
- [x] Add project specification
- [x] Define investment policy
- [x] Define experimental methodology
- [x] Choose benchmark
- [x] Choose market-data provider
- [x] Define transaction-cost assumptions
- [x] Define initial portfolio rules
- [x] Define success metrics
- [x] Define repository structure

Phase 0 documentation:

- [`docs/project-specification.md`](docs/project-specification.md) — product scope, requirements, and roadmap
- [`docs/investment-policy.md`](docs/investment-policy.md) — permitted assets, risk limits, and trade rules
- [`docs/experimental-methodology.md`](docs/experimental-methodology.md) — hypotheses, accounting, metrics, and integrity controls
- [`docs/data-and-benchmark.md`](docs/data-and-benchmark.md) — benchmark and data-provider decisions
- [`docs/architecture.md`](docs/architecture.md) — target system and repository structure
- [`docs/decisions/0001-phase-zero-baseline.md`](docs/decisions/0001-phase-zero-baseline.md) — architectural decision record
- [`rationale.md`](rationale.md) — comparisons and rationale for every major experimental and technical choice

## Phase 1

- [x] Initialize the Next.js and FastAPI applications
- [x] Configure PostgreSQL, SQLAlchemy, and Alembic
- [x] Model portfolios, assets, positions, transactions, and cash-ledger entries
- [x] Implement BUY and SELL accounting with costs and FX
- [x] Calculate cash, moving average cost, realized P&L, and unrealized P&L
- [x] Protect transaction and cash history with append-only database triggers
- [x] Test the domain, repository, API, migration lifecycle, and production web build

The implementation contract, API routes, local setup, tests, and deliberate phase boundaries are documented in [`docs/phase-1.md`](docs/phase-1.md).

## Phase 2

- [x] Add a provider-neutral EODHD adapter for ticker/name/ISIN lookup and historical EOD prices
- [x] Separate stable assets from exchange listings and provider symbols
- [x] Cache raw price, adjusted-close, FX, and exchange-session observations in PostgreSQL
- [x] Preserve upstream corrections as append-only revisions with payload checksums
- [x] Distinguish expected-session gaps from holidays and expose a data-quality queue
- [x] Produce idempotent daily portfolio snapshots with exact input lineage and freshness
- [x] Add operator/backfill commands and a scheduled Render daily job
- [x] Test provider failures, invalid data, cache hits, corrections, holidays, FX, and snapshots

The data contract, worker commands, schedule, exception workflow, API routes, and remaining Day Zero gates are documented in [`docs/phase-2.md`](docs/phase-2.md).

## Phase 3

- [x] Build responsive overview, performance, portfolio, and methodology navigation
- [x] Show portfolio value, daily/total return, benchmark, excess return, and cash
- [x] Add an accessible portfolio-versus-`IWDA` chart with a tabular alternative
- [x] Add holdings, local/EUR values, P&L, weights, and market-data freshness
- [x] Expose preview, empty, live, quality-warning, and fail-closed API-error states
- [x] Generate the TypeScript API contract from FastAPI OpenAPI and verify drift in CI
- [x] Add a Figma-ready design/token handoff and branded social preview
- [x] Test components/data states and validate the production Next.js build
- [ ] Connect the external Figma and Vercel projects and verify the public production URL

The design specification, data-state contract, configuration, deployment steps, and deliberate Phase 4/5 boundaries are documented in [`docs/phase-3.md`](docs/phase-3.md).

## Guiding principles

1. **No hindsight.** A decision is sealed before its execution price exists.
2. **Append, never rewrite.** Corrections and thesis changes are new records linked to the records they supersede.
3. **Same clock, same cash.** Portfolio and benchmark begin with the same capital and are valued on the same dates in EUR.
4. **Net results.** Costs, cash, dividends, corporate actions, and currency conversion are part of performance.
5. **Reproducible calculations.** Stored inputs plus versioned calculation code must reproduce every published number.
6. **A loss is still a result.** Engineering success is independent of investment outperformance.

## Roadmap

| Phase | Outcome |
| --- | --- |
| 0 — Definition | Rules and methodology are explicit before implementation |
| 1 — Portfolio engine | Tested cash, position, cost-basis, and P&L accounting |
| 2 — Market data | Daily market data and portfolio snapshots |
| 3 — Dashboard | Public portfolio and benchmark tracker |
| 4 — Decision system | Immutable, queryable decision history |
| 5 — Analytics | Return, risk, attribution, and behavior metrics |
| 6 — AI research | Structured and reproducible model research |
| 7 — AI manager | Policy-constrained portfolio decisions |
| 8 — Committee | Recorded multi-agent debate and final decisions |
| 9 — Automation | Reviews, monitoring, and scheduled reporting |
| 10 — Public experiment | Independently inspectable experiment |

## Implementation stack

- Next.js and TypeScript for the web application
- FastAPI and Python for APIs, accounting, and analytics
- PostgreSQL for transactional and audit data
- Background jobs for market-data ingestion and daily valuation
- Docker for local development; GitHub Actions for automated checks
- Vercel for the web app, Render for API/jobs, and Supabase for PostgreSQL and private evidence storage

The Phase 3 dashboard is implemented on the modular monorepo foundation. See the [architecture document](docs/architecture.md) for boundaries and the [project rationale](rationale.md) for the alternatives considered.

## Status

Phases 0–2 are complete, and the Phase 3 dashboard implementation is complete and deployment-ready. Its native Figma artifact and public Vercel URL remain external release steps. The experiment has **not** started: provider/public-display entitlement, corporate-action accounting, a Day Zero timestamp, model version, initial portfolio, and market-condition snapshot have not been sealed yet.

## License

Code and original documentation are released under the [MIT License](LICENSE). Third-party market data remains subject to its provider's terms and must not be committed to this repository.
