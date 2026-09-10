# Phase 3 dashboard

## Outcome

Phase 3 turns the Phase 1 web shell into a responsive public portfolio tracker backed by the immutable snapshot and market-data APIs from Phase 2. It makes the experiment's primary question visible first: what the same starting capital is worth in the AI portfolio and in `IWDA`.

The implementation includes:

- anchored overview, performance, portfolio, and methodology navigation;
- portfolio value, daily return, total return, benchmark return, excess return, and cash summaries;
- a responsive portfolio/benchmark value chart with a keyboard-readable HTML table alternative;
- realized and unrealized P&L visualization;
- holdings with quantities, local prices, local/EUR values, weights, P&L, and price freshness;
- open market-data warnings and snapshot revision/calculation metadata;
- explicit preview, empty, live, and API-error states;
- visible boundaries for decision history (Phase 4) and versioned risk analytics (Phase 5);
- Open Graph and social-card metadata; and
- unit/component tests plus production build validation in CI.

## Design handoff

The implemented dashboard is the canonical reviewed frame for Phase 3. These tokens allow the screen to be reproduced as Figma components without estimating from a screenshot.

| Token | Value | Use |
| --- | --- | --- |
| Canvas | `#07100e` | Page background |
| Surface | `#0c1714` | Main panels |
| Raised surface | `#101e1a` | Nested/interactive surfaces |
| Primary text | `#f0f4ec` | Headings and primary values |
| Muted text | `#93a39c` | Labels and supporting copy |
| Border | `#26332e` | Panel and table boundaries |
| Portfolio signal | `#c7f36b` | AI series, gains, active focus |
| Benchmark | `#7ccbd8` | `IWDA` comparison series |
| Warning | `#f4c86a` | Preview, stale data, pending state |
| Loss/error | `#ff897c` | Negative values and live-data failures |
| Display type | Inter/system sans, 46–109 px responsive | Primary experiment statement |
| Numeric type | System monospace | Money, returns, revisions, table values |

Desktop uses a 1440 px maximum frame with 34 px gutters, a five-cell metric strip, a full-width primary chart, paired secondary panels, and a full-width holdings table. Tablet collapses summary cells into two columns and secondary panels into one. At 620 px, metrics become a single column and holdings change from a wide table into labelled stacked records while retaining table semantics in the DOM.

The visual language is deliberately editorial and analytical: square borders, restrained color, visible grid rhythm, no decorative dashboard-card collage, and no animation in financial charts. The generated social card is stored at `apps/web/public/og.png` (1200 × 630).

A native Figma file and production deployment URL require access to their respective external projects and are not stored in this repository. The token/layout table above is the handoff contract; any later Figma version must match the tested implementation or record an intentional design change.

## Data flow and states

The page is a request-time Next.js Server Component. It reads server-only environment variables, retrieves typed JSON from FastAPI, selects the highest snapshot revision for each valuation date, and passes a serializable view model to the chart island. No API URL or portfolio identifier is exposed as a `NEXT_PUBLIC_` browser variable.

| State | Trigger | Public behavior |
| --- | --- | --- |
| Preview | API base URL or portfolio ID absent | Fixed fixture with prominent “illustrative pre-launch” disclosure |
| Live | Portfolio and one or more snapshots load | Latest revisions, holdings, lineage, freshness, and issues are shown |
| Empty | Portfolio exists with no snapshots | No fabricated results; first-valuation guidance is shown |
| Error | Live configuration exists but any required request fails | Financial values and holdings are hidden; a concise error is shown |

This distinction matters: a production outage must never look like a successful investment result.

## API contract

FastAPI remains the source of the API contract. Run:

```bash
.venv/bin/python scripts/export_openapi.py
npm run generate:api-client
```

The first command produces `schemas/openapi.json`; the second produces `packages/api_client/src/schema.d.ts`. CI repeats both commands and fails if the committed artifacts change. The web application imports schema types from the generated workspace package and does not maintain parallel response interfaces.

## Benchmark boundary

When `AIL_WEB_BENCHMARK_LISTING_ID` is configured, Phase 3 plots the latest stored `IWDA` adjusted close on each common snapshot date, rebased to the portfolio's starting capital. The label explicitly says that this is indicative until the benchmark ledger is launched.

This is not a substitute for the frozen net benchmark methodology. The authoritative series still requires benchmark units, simulated execution, cash residual, fees, FX, distributions/corporate actions, and versioned benchmark snapshots. Those Day Zero requirements cannot be recreated silently in browser code.

## Configuration

Copy `.env.example` to `apps/web/.env.local` or supply the variables through the hosting platform:

| Variable | Required | Purpose |
| --- | --- | --- |
| `AIL_WEB_API_BASE_URL` | For live mode | Server-reachable FastAPI base, including `/api/v1` |
| `AIL_WEB_PORTFOLIO_ID` | For live mode | Public experiment portfolio UUID |
| `AIL_WEB_BENCHMARK_LISTING_ID` | For comparison | Stored `IWDA` listing UUID |
| `AIL_WEB_SITE_URL` | Production | Canonical HTTPS origin for social metadata |

Without the first two variables the app intentionally starts in preview mode. With them configured, an unreachable or invalid API produces the error state.

## Local verification

```bash
npm ci
npm run generate:api-client
npm run dev:web
```

For the complete Phase 3 gate:

```bash
npm run lint:web
npm run typecheck:web
npm run test:web
npm run build:web
```

## Vercel deployment

Vercel remains the selected frontend host. Create/import the project with `apps/web` as its Root Directory and leave source files outside the root enabled so npm workspace metadata and `packages/api_client` remain available. `apps/web/vercel.json` runs the locked root install and workspace build. Configure the four variables above and add the deployed HTTPS origin to the API's `AIL_CORS_ORIGINS` before publication.

The repository is deployment-ready, but connecting a Vercel account/project and publishing a URL are external release operations. They are deliberately not represented as complete until a real deployment URL has been verified.

## Acceptance and phase boundaries

| Requirement | Phase 3 status |
| --- | --- |
| Primary portfolio/benchmark comparison immediately visible | Implemented |
| Navigation, portfolio summary, holdings, P&L, responsiveness | Implemented |
| Currency, period, costs, timestamps, freshness, warnings | Implemented |
| Chart text/table alternative and keyboard focus | Implemented |
| Figma-ready components/tokens | Documented; native Figma artifact requires project access |
| Public Vercel URL | Deployment-ready; requires project connection and production configuration |
| Holding confidence/current thesis and recent decisions | Correctly withheld until Phase 4 owns immutable decision records |
| Maximum drawdown and Sharpe | Correctly withheld until Phase 5 owns versioned analytics |

The dashboard performs display-only arithmetic (formatting, weights, daily deltas, and rebasing stored benchmark observations). Python snapshots remain authoritative for cash, P&L, positions, and total return.
