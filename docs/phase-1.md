# Phase 1 — Portfolio engine

- Status: Complete
- Completed: 10 September 2026
- Experiment state: `prelaunch`

Phase 1 provides a tested accounting foundation for fictional trades. It does not start the experiment, select securities, ingest live prices, or authorize real-money trading.

## Delivered scope

- A Next.js App Router application shell with strict TypeScript, linting, and a production build.
- A versioned FastAPI `/api/v1` service with OpenAPI documentation.
- A framework-independent Python domain package for exact-decimal portfolio accounting.
- SQLAlchemy models and an Alembic migration for portfolios, assets, positions, transactions, and the cash ledger.
- PostgreSQL 17.11 in Docker Compose, with health checks and environment-based configuration.
- BUY and SELL execution with adverse slippage, commission, non-EUR FX fees, immediate paper settlement, and non-negative cash enforcement.
- Moving weighted-average cost, partial and full disposal accounting, realized P&L, market valuation, unrealized P&L, and total return.
- Append-only PostgreSQL triggers for transactions and cash-ledger rows; current positions remain rebuildable projections.
- Unit, repository, and HTTP integration tests plus automated lint, type, build, migration, and coverage gates.

## Accounting contract

Python `Decimal` and PostgreSQL `numeric` are authoritative. Inputs may use up to eight decimal places for quantities and prices, twelve for FX/rates, and two for base-currency money. Calculated money is rounded to cents with round-half-even.

For a BUY:

```text
execution price = reference price × (1 + slippage rate)
cash debit      = EUR gross notional + commission + applicable FX fee
new cost basis  = old cost basis + cash debit
```

For a SELL:

```text
execution price    = reference price × (1 - slippage rate)
cost basis removed = existing cost basis × sold quantity / existing quantity
net proceeds       = EUR gross notional - commission - applicable FX fee
realized P&L       = net proceeds - cost basis removed
```

For valuation:

```text
market value   = quantity × quoted price × EUR FX rate
unrealized P&L = market value - remaining cost basis
total value    = cash + sum(position market values)
```

The fixed cost assumptions come from [`experiment-policy.json`](../config/experiment-policy.json): 5 bps adverse slippage, `max(EUR 1, 10 bps of notional)` commission, and a 20 bps fee for non-EUR listings.

## Persistence model

| Table | Role | Mutation rule |
| --- | --- | --- |
| `portfolios` | Starting capital, cash, realized P&L, policy/version | Updated transactionally as a projection |
| `assets` | Stable instrument/listing identity | Reference data; unique by listing identifiers |
| `positions` | Current quantity, cost basis, and realized P&L by asset | Rebuildable projection; removed after a full exit |
| `transactions` | Full modeled execution and itemized costs | Append-only in PostgreSQL |
| `cash_ledger_entries` | Initial capital and every trade cash movement | Append-only in PostgreSQL |

The repository locks the portfolio and affected position, performs the domain calculation, and persists the transaction, cash movement, position, and portfolio totals in one database transaction. Failed buys and oversells leave no economic record or cash mutation.

## HTTP surface

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/health` | Process liveness |
| `GET` | `/api/v1/ready` | Database readiness |
| `POST` | `/api/v1/portfolios` | Open a fictional cash portfolio |
| `GET` | `/api/v1/portfolios/{id}` | Read portfolio accounting state |
| `POST` | `/api/v1/assets` | Register a public equity or UCITS ETF listing |
| `GET` | `/api/v1/assets/{id}` | Read an asset |
| `GET` | `/api/v1/portfolios/{id}/positions` | List open positions |
| `GET` | `/api/v1/portfolios/{id}/transactions` | Read the transaction chronology |
| `GET` | `/api/v1/portfolios/{id}/transactions/{transaction_id}` | Read one execution record |
| `POST` | `/api/v1/portfolios/{id}/transactions` | Execute a validated fictional BUY or SELL |

Interactive API documentation is available at `http://localhost:8000/docs` while the API is running.

## Run locally

Prerequisites are Python 3.13, Node.js 24 or 26, npm, and Docker with Compose.

```bash
cp .env.example .env
docker compose up -d postgres

python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
alembic upgrade head
uvicorn ai_investment_lab.api.main:app --reload
```

In a second terminal:

```bash
npm ci
npm run dev:web
```

Run the same core gates used by CI:

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy apps/api/src packages/db/src packages/domain/src
.venv/bin/pytest
npm run lint:web
npm run typecheck:web
npm run build:web
```

## Deliberate boundaries

- The trade endpoint accepts a caller-supplied reference price only as a Phase 1 verification interface. Phase 2 must derive eligible prices and FX observations from stored provider data.
- `decision_id` is temporarily optional because sealed decisions arrive in Phase 4. It must become required before Day Zero.
- Dividends, splits, other corporate actions, market calendars, and daily snapshots depend on Phase 2 market data and are not silently simulated here.
- Portfolio concentration, sector, minimum-cash policy, and turnover checks require a time-consistent valuation context and are added with the execution workflow before autonomous decisions.
- SQLite is used only for fast deterministic repository/API tests. PostgreSQL is the production contract, and CI exercises the Alembic upgrade/check/downgrade lifecycle against PostgreSQL 17.11.

These boundaries mean Phase 1 satisfies the project brief's portfolio-engine milestone while avoiding fake market-data and decision provenance. None may remain unresolved at Day Zero.
