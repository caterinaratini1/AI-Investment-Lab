# Architecture and repository structure

## 1. Architecture principles

- Keep portfolio accounting and policy enforcement in the Python domain layer, independent of HTTP and database frameworks.
- Use PostgreSQL as the system of record; neither frontend state nor model output is authoritative.
- Treat external market/model providers as replaceable adapters.
- Generate the TypeScript API client from FastAPI's OpenAPI document to avoid parallel hand-written contracts.
- Use an append-only ledger and audit tables for economic and experimental events.
- Start as a modular monolith. Separate deployable services only when operations require it.

## 2. Target runtime

```text
Next.js web
    |
    | generated HTTP client
    v
FastAPI API -------------- PostgreSQL
    |                           ^
    | domain services           |
    v                           |
background worker --------------+
    |
    +-- market-data adapter (EODHD)
    +-- macro adapter (ECB)
    +-- model adapter (post-MVP)
    +-- content-addressed raw evidence storage
```

The API owns commands and queries. The worker owns scheduled ingestion, snapshot calculation, reconciliation, and later model workflows. Both call the same domain/application packages so accounting rules exist once.

## 3. Planned repository layout

```text
AI-Investment-Lab/
├── apps/
│   ├── web/                    # Next.js application
│   ├── api/                    # FastAPI entry point and routes
│   └── worker/                 # scheduled/background jobs
├── packages/
│   ├── domain/                 # Python accounting and policy rules
│   ├── data_providers/         # market, FX, macro adapters
│   ├── db/                     # SQLAlchemy models, repositories, migrations
│   └── api_client/             # generated TypeScript client
├── config/                     # versioned non-secret experiment policy
├── schemas/                    # durable JSON/OpenAPI schemas
├── docs/
│   └── decisions/              # architecture/experiment decision records
├── tests/
│   ├── fixtures/               # reviewed deterministic market/accounting cases
│   ├── integration/
│   └── e2e/
├── infra/                      # Docker and deployment definitions
├── scripts/                    # repeatable developer/operations commands
└── .github/workflows/          # CI checks
```

Directories are created when their phase begins; empty scaffolding is intentionally not committed in Phase 0.

## 4. Dependency direction

`domain` has no dependency on FastAPI, Next.js, EODHD, or a particular database. Application use cases depend on domain interfaces. Provider and persistence packages implement those interfaces. API and worker entry points compose them.

This boundary makes three future changes routine rather than invasive:

- replacing the market-data provider;
- running deterministic accounting tests without network/database access;
- comparing model providers while preserving one decision schema.

## 5. Persistence and immutability

PostgreSQL uses normal relational tables for source-of-truth records. Economic events use a double-entry-style cash/security ledger or equivalent invariant-preserving journal. Current positions are projections, not independently editable truth.

Sealed decisions, model runs, sources, transactions, policy versions, and calculation runs reject UPDATE and DELETE for the application role. Corrections are linked append-only records. Database migrations and privileged maintenance remain possible but are audited and never used to revise experimental history silently.

Large licensed raw responses and evidence files belong in private object storage. PostgreSQL retains metadata, access-controlled URI, media type, byte length, and SHA-256 checksum.

## 6. Technology baseline

| Area | Choice |
| --- | --- |
| Web | Next.js 16 App Router, React 19, and TypeScript 5.9; shell initialized in Phase 1 |
| API | Python 3.13, FastAPI 0.141, and Pydantic 2.13 |
| Persistence | PostgreSQL 17 with SQLAlchemy 2.0 and Alembic 1.19 |
| Numeric model | Python `Decimal` and PostgreSQL `numeric` with explicit scale |
| Jobs | Render cron runs idempotent Python commands; PostgreSQL records runs; no queue/broker until continuous workflows require one |
| Local environment | Docker Compose for PostgreSQL; apps runnable directly for fast iteration |
| Testing | Pytest for Python, Vitest for web units, and Playwright for critical end-to-end flows |
| CI | GitHub Actions: lint, type-check, tests, schema validation, generated-client drift, and migration checks |

Phase 2 direct and transitive dependencies are version-locked in the npm and Python lock manifests. Later-phase dependencies are selected and locked only when their components are implemented.

## 7. Environments and delivery

- **Local:** synthetic fixtures by default; provider calls opt-in with developer credentials.
- **Test/CI:** deterministic fixtures only; network access is not required.
- **Staging:** provider sandbox/limited credentials and disposable database.
- **Production:** least-privilege credentials, managed PostgreSQL, private evidence storage, scheduled backups, and observable jobs.

The initial deployment target is Vercel for Next.js, Render for the Dockerized FastAPI API plus cron/background workloads, and Supabase for managed PostgreSQL and private evidence storage. Services must use compatible European regions where the platforms permit it. Provider-specific features stay behind adapters: PostgreSQL remains accessible through SQLAlchemy/Alembic, and evidence through an object-storage interface.

Supabase database backups do not include Storage objects, so the production runbook must back up the database and private evidence independently and test both restores. The complete comparison and reasons for these infrastructure choices are in [`../rationale.md`](../rationale.md).

## 8. Phase boundaries

Phase 1 created `apps/api`, `packages/domain`, `packages/db`, migrations, accounting tests, and the minimal `apps/web` shell required by the original brief. Phase 2 adds `packages/data_providers`, `apps/worker`, versioned market-data persistence, daily snapshot APIs, and the Render schedule. Phase 3 turns the shell into the data-backed dashboard and generates its API client. This ordering keeps authoritative financial behavior downstream of tested accounting contracts while proving the web toolchain early.
