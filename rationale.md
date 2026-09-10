# Rationale for major project choices

- Status: Phase 0 baseline plus Phase 1 implementation record
- Decision date: 10 September 2026
- Policy version: `0.1.0`

This document explains why AI Investment Lab made each major experimental, financial, architectural, and infrastructure choice. “Best” means the best fit for this experiment's goals and constraints—not the universally best technology, provider, benchmark, or investment strategy.

The choices are evaluated against six priorities, in order:

1. **Experimental integrity:** prevent hindsight and preserve the exact decision-time record.
2. **Financial correctness:** make cash, costs, corporate actions, currencies, and returns reproducible.
3. **Auditability:** let an independent reviewer understand and recalculate the result.
4. **Delivery speed:** keep a solo/small-team MVP feasible without creating avoidable rework.
5. **Portability:** avoid placing core rules behind a vendor-specific API or model.
6. **Cost and operability:** keep the first experiment affordable and understandable in production.

## Decision summary

| Area | Choice |
| --- | --- |
| Experiment | Prospective, single AI-managed paper portfolio versus a frozen passive benchmark |
| Capital and currency | EUR 10,000; all reporting in EUR |
| Initial duration | 12 months, with continued observation encouraged afterward |
| Benchmark | `IWDA` on Euronext Amsterdam, an accumulating UCITS proxy for MSCI World |
| Investment style | Benchmark-aware, long-only quality at a reasonable price (QARP) |
| Universe | Liquid public equities, UCITS ETFs, and cash |
| Execution | First regular-session open strictly after a decision is sealed |
| Costs | 10 bps commission with EUR 1 minimum, 5 bps adverse slippage, 20 bps non-EUR FX fee |
| Market data | EODHD worldwide end-of-day data; ECB for €STR |
| Accounting | Moving weighted-average cost in EUR; exact decimals; round-half-even at monetary boundaries |
| Frontend | TypeScript, React, Next.js App Router |
| Backend | Python, FastAPI, Pydantic |
| Database | PostgreSQL, hosted initially by Supabase |
| Persistence | SQLAlchemy and Alembic; exact `numeric`/`Decimal` arithmetic |
| Runtime baseline | Node.js 24 LTS for CI/deployment; Python 3.13; PostgreSQL 17.11 |
| Jobs | Same Python codebase run as Render cron jobs; background worker when continuous workflows arrive |
| Hosting | Vercel for web; Render for API/jobs; Supabase for database/private evidence |
| Architecture | Modular monolith in a monorepo with provider adapters |
| API contract | FastAPI-generated OpenAPI and generated TypeScript client |
| Testing | Pytest for domain/API, Vitest for web units, Playwright for critical end-to-end flows |
| CI/CD | GitHub Actions with locked dependencies, migrations, schema checks, and deterministic fixtures |
| AI integration | Deferred until the portfolio engine works; provider-neutral structured output interface |

## 1. Prospective experiment instead of a backtest

### Options considered

| Option | Strength | Main weakness here |
| --- | --- | --- |
| Historical backtest | Fast feedback and many market regimes | Easy to leak future knowledge through model training, revised data, survivor lists, or prompt iteration |
| Real-money portfolio | Maximum realism | Financial, legal, operational, and safety consequences obscure the research question |
| Prospective paper portfolio | Clean decision timestamps with no capital risk | Only one realized market path and simulated execution |
| Multiple models from Day Zero | Direct model comparison | Multiplies data, orchestration, and debugging variables before accounting is proven |

### Choice and rationale

The first experiment is a **prospective paper portfolio**. This is the strongest design for the central claim because every decision can be sealed before its outcome exists, while mistakes cannot lose real money. A conventional backtest would be useful for testing accounting code, but weak evidence for an LLM's investment ability: the model may already know the historical period and point-in-time datasets are difficult to reconstruct perfectly.

One model/portfolio comes first so an accounting or provenance defect cannot contaminate several experiments simultaneously. Multi-model comparison becomes valuable only after all contestants can receive identical point-in-time inputs and use the same execution engine.

## 2. EUR 10,000 base capital and a 12-month initial period

### Options considered

- **USD base currency:** aligns with many market-data examples and US securities, but is not the natural cash account for a Europe-based experiment.
- **EUR base currency:** makes costs and the benchmark vehicle directly interpretable while still exposing foreign holdings to genuine currency risk.
- **A very large fictional portfolio:** reduces minimum-commission impact but makes liquidity and retail execution assumptions less intuitive.
- **Three to six months:** faster result, but dominated by noise and too short for fundamental theses.
- **Three to five years:** more meaningful evidence, but too long for an initial product milestone.

### Choice and rationale

EUR 10,000 is large enough to construct a diversified fractional-share portfolio and small enough that retail-style fees matter. EUR reporting also forces the system to model FX honestly instead of treating every local-currency return as comparable.

Twelve months is the best initial commitment because it is operationally achievable and spans earnings cycles, while remaining a clearly limited sample. It is not claimed to prove persistent alpha. The public dashboard should continue beyond the initial report when feasible, because a longer track record is more informative than redefining success after month twelve.

## 3. Benchmark: IWDA rather than a raw index or US benchmark

The conceptual comparison is the MSCI World Index. MSCI describes it as developed-market large- and mid-cap exposure covering about 85% of free-float-adjusted market capitalization in each included country. The executable proxy is the EUR Euronext Amsterdam listing of the iShares Core MSCI World UCITS ETF USD (Acc): ticker `IWDA`, MIC `XAMS`, ISIN `IE00B4L5Y983`. See the [MSCI World overview](https://www.msci.com/indexes/index/990100/msci-world-index) and [iShares fund listings](https://www.ishares.com/uk/individual/en/products/251882/ishares-msci-world-ucits-etf).

### Options considered

| Option | Advantages | Why it was not selected |
| --- | --- | --- |
| Official MSCI World net-return series | Closest to the named index | Licensing/redistribution and access are less straightforward; it is not directly tradable |
| `IWDA` Amsterdam EUR | UCITS, liquid, accumulating, EUR-traded, directly investable | Has tracking difference, expenses, and market-price/NAV effects |
| `SWDA` London GBP/USD listing | Same underlying fund | Adds an avoidable benchmark-currency conversion |
| `VWCE` / FTSE All-World proxy | Includes emerging markets and is broadly diversified | Changes the brief's MSCI World/developed-market question |
| S&P 500 ETF | Extremely liquid and easy to source | US-only exposure is not the stated global benchmark |
| Custom basket of regional ETFs | Full control | Rebalancing methodology adds arbitrary choices and maintenance |

### Choice and rationale

`IWDA` is the best benchmark for this experiment because it represents an **attainable passive alternative** for a EUR-based investor. It can follow the same order, transaction-cost, timestamp, fractional-share, and valuation rules as the AI portfolio. Its accumulating structure incorporates fund income into its price, and the EUR listing avoids an artificial benchmark FX transaction without eliminating the underlying companies' currency exposures.

Using the ETF intentionally changes the claim from “beat a frictionless index calculation” to “beat a passive vehicle an investor could have bought.” Tracking difference and fund fees are disclosed rather than treated as errors. The system never silently splices a replacement if `IWDA` becomes unavailable.

## 4. Investment strategy: benchmark-aware QARP

### Strategy selected

The initial strategy is **benchmark-aware, long-only quality at a reasonable price (QARP)**. It looks for durable businesses or diversified UCITS ETFs whose expected return is attractive relative to their valuation and identifiable risks. Company analysis emphasizes:

- balance-sheet resilience and cash generation;
- durable competitive position and sensible capital allocation;
- revenue, margins, and returns on capital;
- valuation using more than one defensible method;
- a plausible route for mispricing to close or compounding to become visible;
- explicit evidence that would invalidate the thesis.

Normal intended holding periods are 6–24 months. The portfolio targets 8–15 holdings when enough valid ideas exist, may hold cash, and does not trade merely to stay active. Benchmark weights inform risk analysis but do not dictate holdings.

### Options considered

| Strategy | Strength | Weakness for this first experiment |
| --- | --- | --- |
| Deep value | Clear valuation discipline | Value traps and catalysts can take longer than 12 months; accounting comparability across markets is difficult |
| High growth | AI can synthesize qualitative narratives | Expectations and terminal values dominate, making theses fragile and easy to rationalize after the fact |
| Pure momentum | Simple, testable, and often systematic | Tests a price rule more than an AI research/decision process |
| Market neutral/long-short | Better isolation of security selection | Requires shorting, leverage, borrow costs, and more complex risk controls prohibited by the brief |
| Frequent event trading | Many decisions and faster feedback | EOD data and simulated fills become unrealistic; costs and news latency dominate |
| Passive/index enhancement | Lower tracking error | Too close to the benchmark to test meaningful active decision-making |
| QARP | Combines business quality, valuation, risk, and medium-term evidence | Requires disciplined definitions to prevent “quality” becoming a vague narrative |

### Why QARP is the best fit

QARP creates the richest auditable test of an AI portfolio manager without requiring prohibited instruments or intraday infrastructure. Its inputs—financial statements, competitive evidence, valuation assumptions, risks, and invalidation tests—can be recorded as structured claims and revisited later. It also discourages the two failure modes most likely in an LLM experiment: persuasive stories with no valuation discipline, and cheap-looking securities with structurally deteriorating businesses.

The approach is not claimed to be the best strategy in all markets. It is the best match for the product objective: evaluating the quality of research and portfolio reasoning, not merely automating a known factor formula.

## 5. Long-only liquid equities, UCITS ETFs, and cash

### Options considered

- Adding options/futures would improve hedging but introduce nonlinear valuation, margin, expiry, and implied-volatility assumptions.
- Short selling would broaden opportunity but requires borrow availability, borrow fees, recall rules, and potentially unbounded loss.
- Cryptocurrency would provide continuous prices but changes the economic universe and custody assumptions.
- Illiquid small caps could offer greater inefficiency but make a single opening-price fill implausible.

### Choice and rationale

Long-only liquid securities keep the result attributable to asset selection and sizing. The EUR 1 billion equity market-cap floor and EUR 5 million 20-session median value-traded floor make full simulated fills reasonable for a EUR 10,000 portfolio. UCITS eligibility gives the ETF universe a consistent European regulatory boundary. Cash is a real portfolio decision and therefore remains part of performance rather than being retroactively invested.

## 6. Portfolio constraints

### Chosen limits

| Rule | Choice | Rationale |
| --- | ---: | --- |
| Minimum cash after buys | 5% | Absorbs fees/rounding and prevents accidental leverage while still permitting high deployment |
| Maximum position at trade | 15% | Allows conviction but prevents one idea from deciding the experiment |
| Maximum sector at trade | 30% | Limits disguised concentration without forcing index-like sector weights |
| Minimum new position | 2% | Avoids immaterial “idea collecting” that inflates decision counts |
| Hard maximum holdings | 20 | Keeps every thesis reviewable and attribution meaningful |
| Target holdings | 8–15 | Balances idiosyncratic risk with a genuinely active portfolio |
| Monthly gross turnover | 25% after Day Zero | Permits thesis-driven changes while penalizing churn; initial construction is separately reported |

### Alternatives and rationale

An unconstrained portfolio would make a winning outcome hard to interpret: one oversized winner could masquerade as a repeatable process. Conversely, tight benchmark-relative limits would test closet indexing rather than portfolio management. The selected middle ground permits meaningful active decisions while constraining obvious concentration and activity risks. Limits are checked both before sealing and at modeled execution; passive breaches are recorded, never erased through an automatic unlogged trade.

## 7. Next-session-open execution

### Options considered

| Price convention | Benefit | Problem |
| --- | --- | --- |
| Price visible when decision is written | Intuitive | Requires reliable historical intraday quotes and exact latency evidence |
| Same-day close | Simple EOD accounting | The close may not exist when the decision is sealed, creating lookahead |
| Next-session open | Deterministic separation between decision and outcome | Overnight gaps affect execution, as they would in reality |
| Next-session VWAP | Less sensitive to opening print | Needs licensed intraday trades and a defined participation window |
| Manual arbitrary fill | Flexible | Not reproducible and invites favorable selection |

### Choice and rationale

The first regular-session open strictly after sealing is the cleanest anti-hindsight rule available from end-of-day OHLC data. It creates an unambiguous temporal boundary and makes overnight information risk part of the strategy's actual result. The downside—an opening gap—is a feature of a prospective decision, not a defect to smooth away.

## 8. Transaction-cost model

### Options considered

- **Zero cost:** simple, but structurally favors frequent trading.
- **Flat fee only:** realistic for some brokers, but underprices larger orders.
- **Percentage only:** scales well, but underprices small retail tickets.
- **Broker-specific schedule:** superficially realistic, but ties the experiment to changing promotions, venues, tax domicile, and order routing.
- **Commission + slippage + FX model:** transparent, stable, and covers the main controllable frictions.

### Choice and rationale

Each side pays `max(EUR 1.00, 0.10% of EUR notional)`, plus 0.05% adverse slippage and a 0.20% FX fee for non-EUR listings. This is intentionally conservative and deterministic. It is not a claim about one broker's tariff; it is a fixed experimental penalty that makes turnover costly and comparisons reproducible.

The benchmark pays the same commission and slippage. It buys the maximum affordable fractional quantity, leaving residual cash. Taxes are excluded because investor domicile is not modeled; cash dividends are therefore booked gross, and that limitation is disclosed.

## 9. Market data: EODHD, with ECB for €STR

### Selection criteria

The provider must cover worldwide equities and ETFs, raw EOD OHLCV, corporate actions, FX, exchange/listing metadata, stable API access, and enough history for risk calculations. It must also allow raw versus adjusted prices to be distinguished so dividends are not double-counted.

### Options considered

| Provider/source | Strength | Weakness for this project |
| --- | --- | --- |
| EODHD | Worldwide EOD equities/ETFs, FX, raw/adjusted values, splits/dividends, exchange metadata | Paid global plan and separate commercial/public-display review |
| Twelve Data | Clean API, broad asset classes, explicit adjustment modes | Global EOD coverage is plan-dependent; individual plans restrict redistribution |
| Alpha Vantage | Familiar API and broad indicator catalog | Adjusted daily data is premium and rate/coverage constraints are less convenient for a multi-market portfolio |
| Yahoo Finance libraries | Easy and inexpensive for prototypes | Unofficial interfaces, unstable contracts, ambiguous support, and unsuitable provenance for the system of record |
| Stooq/download sites | Useful free historical datasets | Weaker instrument metadata, support, correction lineage, and contractual API guarantees |
| Direct exchanges/issuers | Most authoritative | Many schemas, licenses, calendars, and integrations defeat MVP simplicity |

EODHD documents worldwide historical EOD coverage, adjusted close, exchange symbol lists, and splits/dividends in its [EOD API](https://eodhd.com/lp/historical-eod-api), [exchange metadata API](https://eodhd.com/financial-apis/exchanges-api-list-of-tickers-and-trading-hours), and [corporate-action/bulk API](https://eodhd.com/financial-apis/bulk-api-eod-splits-dividends).

### Choice and rationale

EODHD is the best single-provider fit for the MVP because its coverage matches the permitted global universe and it supplies the distinct data types needed for a correct ledger. A paid contract is preferable to building an audit claim on an unofficial scraped endpoint.

This selection is conditional on entitlement: the free tier is only for an integration spike, raw responses stay private, and a public-display/commercial license check is required before launch. The provider's [pricing page](https://eodhd.com/pricing) distinguishes personal and commercial use. If the required rights or `IWDA.AS` coverage cannot be confirmed, launch pauses and a new decision record selects a replacement; the system does not silently fall back.

The risk-free input comes directly from the [ECB's €STR publication](https://www.ecb.europa.eu/stats/financial_markets_and_interest_rates/euro_short-term_rate/html/index.en.html), which the ECB publishes without a usage charge or license. This is more defensible for EUR Sharpe and alpha calculations than a US Treasury rate or a hard-coded zero.

## 10. Separate TypeScript frontend and Python backend

### Options considered

| Shape | Advantage | Disadvantage |
| --- | --- | --- |
| Next.js-only full stack | One language and one deployment | Financial/data libraries are stronger in Python; long jobs do not fit naturally in request functions |
| Python server-rendered app | One backend and simple deployment | Weaker fit for an interactive public dashboard and typed UI ecosystem |
| React SPA + Python API | Clean separation and simple static hosting | More client waterfalls, weaker initial rendering/metadata, manual routing conventions |
| Next.js + FastAPI | Best-fit language on each side and strong contracts | Two toolchains and a network boundary |

### Choice and rationale

Next.js plus FastAPI is the best division because this project genuinely has two different workloads. The public product needs responsive tables, charts, accessible routing, shareable pages, and good initial rendering. The financial engine needs exact decimal math, dataframe/statistical tooling, scheduled ingestion, and future LLM research pipelines. Forcing either workload into the other's ecosystem would save a toolchain while increasing domain friction.

The boundary stays disciplined: Python owns financial truth and policy checks; TypeScript owns presentation and interaction. FastAPI's generated OpenAPI contract produces the TypeScript client, preventing two hand-maintained API definitions.

## 11. Frontend: Next.js App Router, React, and TypeScript

### Options considered

- **Vite + React:** excellent for a client-only dashboard, but requires additional decisions for server rendering, metadata, routing, and backend-for-frontend behavior.
- **Remix/React Router framework mode:** strong web fundamentals, but less direct alignment with the proposed Vercel delivery path and project brief.
- **SvelteKit:** concise and capable, but introduces a different ecosystem from the requested React/Next.js direction.
- **Plain templates:** lowest complexity, but poor fit for rich chart/table filtering and later interactive experiment views.

### Choice and rationale

Next.js App Router is the best fit for a public, content-heavy dashboard that also needs interactive islands. It supports server-rendered pages for experiment explanations and decision records while React handles charts and filters. TypeScript catches contract drift and makes generated API types useful end to end. The [Next.js documentation](https://nextjs.org/docs) identifies App Router as the newer router supporting current React features.

Next.js does not calculate authoritative performance metrics. Server Components may fetch them, but the Python engine and stored calculation runs remain the source of truth.

## 12. Backend: Python, FastAPI, and Pydantic

### Options considered

| Option | Strength | Why not chosen |
| --- | --- | --- |
| NestJS/TypeScript | One language across the stack and strong application structure | Less natural financial/data-science ecosystem; duplicates Python later for analytics/AI |
| Django + DRF | Mature batteries, ORM, and admin | More framework surface than needed and less direct schema-first typing |
| Flask | Minimal and flexible | More manual validation, OpenAPI, dependency, and error conventions |
| FastAPI | Typed validation, OpenAPI generation, async I/O, simple container deployment | Requires architectural discipline beyond the framework itself |

### Choice and rationale

Python is the natural home for portfolio accounting, data processing, statistics, and later AI research. FastAPI adds a small typed HTTP layer without forcing the domain model into the framework. Its [documented OpenAPI and Pydantic integration](https://fastapi.tiangolo.com/features/) supports automatic schema and client generation, which is especially valuable across the Python/TypeScript boundary.

FastAPI is not used as a reason to put business rules in route handlers. Routes call application services; the domain package remains importable and testable without HTTP, a database, or network access.

## 13. Database: PostgreSQL rather than SQLite, document storage, or a specialist ledger

### Options considered

| Database | Advantage | Problem here |
| --- | --- | --- |
| SQLite | Excellent local simplicity | Limited concurrent production operation, roles, and server-side immutability controls |
| MongoDB/document DB | Flexible storage for model outputs | Portfolio relations, constraints, transactions, and reproducible joins are inherently relational |
| Dedicated event store | Natural append-only history | Adds unfamiliar infrastructure; projections and analytics still need a query database |
| TimescaleDB | Strong time-series tooling | Premature for one small daily portfolio; PostgreSQL tables/indexes are ample |
| PostgreSQL | Transactions, constraints, exact numeric, JSONB, roles, triggers, mature tooling | Requires schema/migration discipline |

### Choice and rationale

PostgreSQL is the best system of record because the experiment combines strict relations with semi-structured evidence. Foreign keys connect decisions, theses, executions, prices, and calculation lineage. Check/unique constraints enforce invariants. JSONB can retain structured provider/model metadata without weakening the relational core. PostgreSQL's [`numeric` type](https://www.postgresql.org/docs/current/datatype-numeric.html) is designed for exact calculations, and its [constraints](https://www.postgresql.org/docs/current/ddl-constraints.html) reject invalid rows at the database boundary.

The economic ledger is append-only within PostgreSQL; current positions are rebuildable projections. A specialist event store would add operational complexity without improving the evidentiary model at this scale.

## 14. SQLAlchemy, Alembic, and exact decimal arithmetic

Raw SQL alone offers maximum control but makes common persistence work repetitive. A heavy repository abstraction can hide the queries that matter. SQLAlchemy provides explicit transactions, type mapping, and testable repositories while still allowing reviewed SQL where constraints or analytics demand it. Alembic supplies versioned migrations that can be run and audited in CI.

Money, quantities, prices, and FX rates use Python `Decimal` and PostgreSQL `numeric` with explicit precision/scale. Binary floating point is rejected for ledger calculations because apparently tiny representation errors can break cash reconciliation, equality constraints, and reproducibility.

## 15. Managed PostgreSQL: Supabase

### Options considered

| Host | Strength | Tradeoff |
| --- | --- | --- |
| Supabase | Full PostgreSQL, dashboard, pooling, backups, RLS, private object storage | Another vendor and storage backups are separate from database backups |
| Neon | Excellent serverless scaling, branching, and restore workflow | Extra object-storage provider still required; scale-to-zero is not important for scheduled ingestion |
| Render Postgres | Keeps API and database on one platform | Fewer integrated data/evidence management features than Supabase for this product |
| AWS RDS | Deep control, mature operations, broad compliance | Highest configuration and operational burden for an MVP |
| Self-hosted PostgreSQL | Maximum control and portability | Backup, patching, monitoring, and recovery become project work rather than product work |

### Choice and rationale

Supabase is the best MVP data platform because it remains a real PostgreSQL database rather than a proprietary database abstraction, while providing managed operations and [private, RLS-controlled object storage](https://supabase.com/docs/guides/storage/buckets/fundamentals) for evidence. The application still connects through SQLAlchemy and Alembic, so the database can move later. Supabase documents a [full PostgreSQL database, pooling, RLS, daily backups, and optional PITR](https://supabase.com/docs/guides/database/overview).

The tradeoff is handled explicitly: [Supabase database backups do not include Storage objects](https://supabase.com/docs/guides/platform/backups). Production therefore needs independent evidence-object backup and restore testing. Free-tier backups are insufficient for the active experiment; the launch checklist must require an appropriate paid plan plus off-platform logical exports.

## 16. Hosting: Vercel for web, Render for API and jobs

### Frontend options

| Host | Strength | Weakness here |
| --- | --- | --- |
| Vercel | First-class Next.js builds, previews, CDN, and function/runtime integration | Vendor-specific conveniences and usage limits |
| Cloudflare Pages/Workers | Global edge and strong cost profile | Some Next.js/runtime behavior differs; Python API still needs another host |
| Render static/web service | One fewer vendor | Gives up the most direct Next.js deployment and preview workflow |
| Self-hosted container | Portable | Adds CDN, TLS, rollout, and preview-environment work |

Vercel is selected because the frontend is explicitly Next.js and benefits from its native build, preview, routing, and caching path. The choice is limited to delivery; data and financial logic do not depend on Vercel APIs.

### Backend/job options

| Host | Strength | Weakness here |
| --- | --- | --- |
| Render | Docker web services, cron jobs, background workers, declarative blueprint | Separate from Vercel/Supabase; paid always-on services when needed |
| Vercel Functions | One hosting vendor and Python runtime support | Request/function lifecycle and cron delivery are a poorer fit for ingestion, retries, and future long AI jobs |
| Railway | Very fast container/service setup | Render's explicit service types and cron single-run behavior better match the planned workload |
| Fly.io | Strong regional container control | More infrastructure/network operations than needed initially |
| AWS ECS/Lambda | Maximum capability | IAM, networking, observability, and cost management are disproportionate for one portfolio |

Render is the best initial backend host because the same Docker image can run as a public FastAPI [web service](https://render.com/docs/service-types), a [scheduled cron job](https://render.com/docs/cronjobs), or later a [background worker](https://render.com/docs/background-workers). Render cron jobs provide run history and a single-active-run guarantee, useful for daily valuation. Application-level idempotency remains mandatory.

Vercel cron was rejected for core accounting jobs because it invokes HTTP functions and may require explicit locking/idempotency handling for overlapping or duplicate delivery; its own [cron documentation](https://vercel.com/docs/cron-jobs/manage-cron-jobs) describes those considerations. Keeping Python jobs beside the Python domain package is simpler and easier to reproduce locally.

## 17. Modular monolith and monorepo

### Options considered

- **Microservices:** independent scaling and deployment, but distributed transactions, message schemas, tracing, and failure handling would dominate an MVP with one portfolio.
- **Single undivided application:** easy initially, but UI, accounting, providers, and jobs become tightly coupled.
- **Modular monolith:** one repository and coherent release, with enforceable internal boundaries and separately runnable entry points.
- **Several repositories:** clear ownership at large organizations, but difficult atomic contract changes for a small team.

### Choice and rationale

A modular monolith in one repository is the best balance. `domain` contains pure accounting/policy rules; `db` and provider packages implement ports; `api` and `worker` compose them; `web` consumes the generated contract. API and worker can deploy as separate processes without becoming separately designed services.

This preserves the option to extract a data-ingestion or AI-workflow service later, but only after real scaling or reliability evidence justifies it. The monorepo also allows a migration, OpenAPI client, backend change, and frontend update to be reviewed atomically.

## 18. Scheduled jobs before a general-purpose queue

Daily EOD ingestion and valuation have predictable schedules and low volume. Render cron jobs running idempotent commands are therefore the initial choice. A permanent Celery/Redis-style queue would add a broker, worker lifecycle, retries, and monitoring before they are necessary.

A background queue becomes justified when model research, report generation, or event-driven monitoring requires long-running concurrent workflows. That is an evolutionary threshold, not a Phase 0 dependency. Job-run rows in PostgreSQL provide idempotency keys, attempt history, input cutoffs, output references, and failure state from the beginning.

## 19. OpenAPI-generated client instead of duplicated contracts

The alternatives are handwritten TypeScript types, a GraphQL schema, tRPC, or OpenAPI generation. Handwritten types inevitably drift. tRPC is strongest in an all-TypeScript stack, which this is not. GraphQL adds resolver/caching complexity without a client-driven graph problem.

FastAPI already emits OpenAPI from validated Pydantic models. Generating a TypeScript client makes that artifact the boundary contract and lets CI detect breaking changes. It is the simplest language-neutral choice and leaves room for future public API consumers.

## 20. Testing and continuous integration

### Choice

- Pytest for deterministic domain invariants, repository, migration, and API tests; property-based tests when the corporate-action state space arrives.
- Vitest and Testing Library for frontend behavior.
- Playwright for a small set of critical browser flows.
- Synthetic, reviewed market-data fixtures in CI; never live provider responses.
- GitHub Actions for formatting, linting, types, unit/integration tests, JSON/OpenAPI validation, migration upgrade/downgrade checks, and generated-client drift.

### Rationale

The accounting engine has a higher correctness burden than the UI, so most tests belong at the pure-domain layer. Property/invariant tests catch combinations such as partial sells, fees, splits, and rounding that example-only tests miss. Live APIs are excluded from CI because mutable upstream data, rate limits, and outages would make builds irreproducible. A separate opt-in provider contract test can monitor the real integration without deciding whether a commit is correct.

[GitHub Actions](https://docs.github.com/en/actions/tutorials/build-and-test-code) is the best fit because the repository already lives on GitHub and needs no separate CI control plane. Deployment occurs only after the same commit passes checks; Day Zero records the exact commit SHA.

## 21. AI is deferred and provider-neutral

### Options considered

- Building agents immediately would create an impressive demo quickly, but any portfolio/accounting flaw would make their output scientifically useless.
- Selecting one provider deeply could accelerate the first workflow, but would entangle prompts, tool calls, and provenance with proprietary response shapes.
- A provider-neutral structured decision contract takes slightly longer but enables fair model comparison later.

### Choice and rationale

No autonomous AI enters the MVP until trades, cash, valuation, benchmark, and immutable decisions work reliably. Later model adapters must produce the same versioned structured schema and store provider, exact model/version, parameters, prompts, tool inputs/outputs, validation results, and raw response.

Provider neutrality does not pretend models are interchangeable; their differences remain recorded. It means those differences do not alter the accounting or audit contract. This is the best preparation for the project's future model-versus-model experiment.

## 22. Append-only records with hashes, not blockchain

Database permissions and triggers prevent normal application updates/deletes to sealed decisions and transactions. Canonical JSON plus SHA-256 makes any content change detectable. Periodic public publication of hashes or a Git commit can add external timestamp evidence.

A blockchain was rejected because it would add keys, fees, chain semantics, and privacy/licensing concerns without making the original data truthful. The core problem is provenance and controlled mutation, which PostgreSQL roles, append-only corrections, private evidence, checksums, backups, and public commit history address more directly.

## 23. MIT code license with data kept separate

MIT is selected for original code and documentation because it is short, permissive, and makes the engineering work easy to inspect and reuse. A copyleft license could require improvements to remain open, but it may discourage integrations and does not solve market-data rights.

Market data, issuer documents, and model/provider outputs remain governed by their own terms. The repository excludes raw provider caches and private evidence. Open-sourcing application code is not permission to redistribute third-party data.

## 24. Decisions intentionally not frozen yet

Some choices would still be false precision and are explicitly deferred:

- exact dependency versions for components not yet implemented; Phase 1 versions are now locked;
- exact Day Zero timestamp and experiment end timestamp;
- AI provider/model/version and generation settings;
- initial securities and their weights;
- queue technology, until scheduled jobs are insufficient;
- a fallback market-data provider, until precedence and discrepancy rules can be defined;
- long-term cloud migration, until measured scale, cost, or compliance requires it.

Deferral is not omission: each item has a trigger and must receive its own append-only decision record before it affects the experiment.

## 25. Phase 1 runtime and dependency baseline

### Options considered

| Decision | Alternatives | Selection reason |
| --- | --- | --- |
| Python 3.13 | 3.12 has a longer compatibility history; 3.14 is newer | 3.13 has mature binary support for the selected data stack, current language features, and matches the container/local baseline without making a newly released interpreter part of the accounting risk |
| Node.js 24 for CI | Node 22 is older LTS; Node 26 is Current rather than the deployment baseline | Node 24 is the stable LTS line for reproducible CI and hosting; the local engine range also permits Node 26 so contributors are not forced backward |
| PostgreSQL 17.11 | PostgreSQL 16 is older; 18.6 is newest | 17.11 is a supported, patched major with the familiar pre-18 official-container data layout and no missing feature needed by this small ledger |
| Current stable application libraries | Broad version ranges or unpinned `latest` | Exact direct versions plus resolved lock manifests make a checkout rebuild the reviewed environment instead of silently changing behavior |

Phase 1 freezes Next.js 16.3.4, React 19.3.0, TypeScript 5.9.3, ESLint 10.9.1, FastAPI 0.141.1, Pydantic 2.13.5, SQLAlchemy 2.0.52, Alembic 1.19.2, and psycopg 3.3.5. npm transitive dependencies live in `package-lock.json`; Python's resolved production and development environments live in `requirements-runtime-lock.txt` and `requirements-lock.txt`, while each package manifest retains its direct runtime contract. PostgreSQL 17.11 is pinned in local Compose and CI. The [PostgreSQL release archive](https://www.postgresql.org/docs/release/) and [official container tags](https://hub.docker.com/_/postgres/tags?name=17.11-alpine) provide the upstream version record.

This is the best reproducibility/maintenance balance for Day Zero preparation. Locking prevents accidental drift; updating remains possible through an explicit reviewed change with all quality gates rerun. Container digests are not frozen yet because development must receive compatible security rebuilds of the same PostgreSQL patch tag; production deployment will record its immutable image digest.

## 26. Moving weighted-average cost rather than FIFO or specific lots

### Options considered

| Method | Strength | Weakness here |
| --- | --- | --- |
| FIFO lots | Familiar tax/accounting convention and retains lot history | Realized P&L depends on an investor jurisdiction the experiment does not model |
| Specific identification | Can mirror a chosen broker lot | Introduces a discretionary lot-selection decision that can manufacture favorable realized outcomes |
| Moving weighted average | Deterministic, order-independent within each purchase batch, and natural for fractional paper positions | Does not reproduce every broker's tax statement |

Moving weighted-average EUR cost is best because this is a performance experiment, not a tax simulation. Every BUY adds gross modeled notional, commission, and FX fee to basis. A partial SELL removes the same fraction of basis as quantity, so selecting a favorable historical lot cannot alter the reported result. The full transaction chronology remains append-only, leaving future lot analytics possible without changing the frozen headline method.

## 27. Append-only events with transactional projections

The main alternatives were (a) recompute all state from the complete ledger on every request, (b) store only mutable balances and positions, or (c) keep immutable events plus mutable projections. Full replay is elegant but unnecessarily expensive and makes concurrency harder at the HTTP boundary. Mutable balances alone are fast but cannot independently explain themselves.

Phase 1 therefore stores every execution and cash movement as append-only history while maintaining portfolio and position projections in the same database transaction. PostgreSQL row locks serialize competing commands for a portfolio. A failed command rolls back the event, cash entry, and projections together. Database triggers reject UPDATE and DELETE on transactions and cash-ledger rows even if a future route is implemented incorrectly.

This hybrid is strongest for the experiment: reads remain simple, but cash and positions can be reconciled or rebuilt from economic events. It is deliberately not called full event sourcing—there is no event bus, generic aggregate framework, or replay infrastructure that Phase 1 does not need.

## 28. Decimal precision and rounding boundaries

The alternatives were binary floating point, arbitrary unbounded decimals, or fixed-precision decimals. Floating point is fast but unsuitable for equality-based cash reconciliation. Unbounded decimals postpone rather than resolve how an execution becomes cents and can let API, Python, and PostgreSQL disagree.

Inputs are validated at explicit scales: eight places for quantities/prices, twelve for rates, and two for money. Intermediate multiplication uses `Decimal`; calculated monetary postings round to cents with round-half-even. Round-half-up is more familiar for retail displays, but systematic upward tie-breaking creates a directional bias across repeated calculations. Round-half-even minimizes that aggregate bias and is consistently available in Python and PostgreSQL-compatible numeric workflows.

The API rejects excess precision instead of silently truncating it. This makes upstream data normalization an observable responsibility and ensures that the stored execution is exactly the execution the caller reviewed.

## 29. A narrow Phase 1 API and early web shell

The engine could have remained a library until the dashboard phase, or Phase 1 could have built a complete CRUD interface. A library alone would leave transaction boundaries, validation, and serialization untested. A full UI would prematurely encode market-data and decision workflows that do not exist yet.

The selected middle path exposes only health/readiness, portfolio and asset creation/read, position/transaction reads, and a fictional trade command. FastAPI owns validation and transaction orchestration; the pure domain package owns accounting. A minimal Next.js shell proves the requested frontend stack and production build without pretending that static placeholders are a portfolio dashboard.

Caller-supplied price and optional `decision_id` are explicitly transitional. Phase 2 replaces manual prices with stored, time-eligible market observations; Phase 4 makes a prior sealed decision mandatory. The endpoint cannot be used for Day Zero until both controls exist. This boundary is better than inventing provenance because it keeps Phase 1 testable while making its limitations impossible to confuse with launch readiness.

## 30. Change rule

Before Day Zero, a major choice may be revised by updating this document, the relevant policy/specification, the machine-readable configuration when applicable, and the decision record in the same commit.

After Day Zero, the original rationale remains. A change requires a new dated decision record that identifies the former choice, evidence, reason, effective timestamp, compatibility impact, and affected metrics. Historical results are never recalculated under a new rule without retaining and labeling the original series.
