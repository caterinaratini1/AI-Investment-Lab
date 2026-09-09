# Project specification

## 1. Purpose

AI Investment Lab is a public, auditable paper-investing experiment designed to answer:

> Can a structured AI portfolio-management process outperform a passive global-equity benchmark, net of simulated costs, without taking unjustifiably greater risk?

The first experiment assigns EUR 10,000 of fictional capital to one portfolio for 12 months. It is a prospective experiment: decisions are captured before execution and cannot be silently revised after market outcomes appear.

## 2. Audiences

- **Observer:** wants to understand what the portfolio owns, why, and whether it is winning.
- **Researcher/reviewer:** wants to reproduce calculations and audit what information existed at decision time.
- **Operator:** enters or approves decisions, monitors data quality, and resolves exceptions without rewriting history.
- **Developer:** extends the system while preserving accounting and experimental integrity.

The initial release has one public portfolio and no end-user trading accounts.

## 3. Product requirements

### Dashboard

The dashboard must make the primary comparison immediately visible: the present value of EUR 10,000 allocated to the AI portfolio versus the same amount allocated to the benchmark.

It shows portfolio value, daily and total return, benchmark and excess return, cash, maximum drawdown, Sharpe ratio, holdings, recent decisions, data freshness, and any unresolved data-quality warning.

### Portfolio

For every current holding, show instrument identity, quantity, average cost, current price and price timestamp, market value in local currency and EUR, portfolio weight, unrealized P&L, return, confidence, and current thesis.

### Decision log

Show an immutable chronology of BUY, HOLD, and SELL decisions. Each record includes:

- creation and sealing timestamps;
- asset identifiers and action;
- target quantity/value/weight and execution rule;
- thesis, transaction reason, expected holding period, confidence, expected upside, risks, and invalidation conditions;
- portfolio state and source manifest supplied to the decision process;
- model provider, model/version, parameters, prompt/template version, raw response, parsed response, and validation result;
- links to resulting transactions, thesis revisions, and any correction records;
- a canonical-content hash.

### Investment detail

Show the original thesis, append-only revisions, confidence history, relevant decisions, trades, major events, current rationale, position P&L, and price history.

### Performance

Show portfolio and benchmark value, cumulative and periodic returns, excess return, drawdown, volatility, Sharpe and Sortino ratios, attribution, turnover, holding periods, transaction-cost drag, results by confidence/sector/thesis, and calculation version.

## 4. MVP boundary

The MVP is a reliable paper-portfolio and audit engine. It must:

1. create the initial cash portfolio;
2. accept fictional BUY and SELL transactions tied to sealed decisions;
3. calculate cash, quantities, average cost, realized and unrealized P&L, and costs;
4. ingest end-of-day market, FX, dividend, and split data;
5. value portfolio and benchmark daily in EUR;
6. persist decisions and display their history;
7. reproduce every displayed result from stored inputs.

Autonomous model research, autonomous execution, multi-agent committees, real-money trading, user brokerage accounts, social features, and strategy marketplaces are outside the MVP.

## 5. Non-functional requirements

### Integrity

- Sealed decisions and executed transactions are append-only.
- Database constraints, not only UI behavior, enforce invariants.
- Corrections retain the erroneous record and state the reason, author, and replacement.
- Every external fact has source, retrieval time, observation time, and effective time when available.
- All timestamps are stored in UTC and rendered with an explicit timezone.

### Reproducibility

- Monetary arithmetic uses fixed-precision decimals; never binary floating point.
- Each snapshot identifies its market-data records and calculation-code version.
- Re-running a historical calculation from the same inputs produces the same result.
- Raw provider responses are retained privately with checksums; licensed data is not committed to Git.

### Reliability and security

- Ingestion and execution commands are idempotent.
- Secrets are supplied through environment variables and never stored in source control.
- Database backups and restoration are tested before public launch.
- A data-quality failure freezes affected valuations and is displayed; it never silently substitutes a guessed price.

### Accessibility and clarity

- Core pages meet WCAG 2.2 AA goals.
- Charts have tabular/text alternatives.
- Performance always states period, currency, price timestamp, and whether costs are included.
- Every public page carries a paper-trading/not-financial-advice notice.

## 6. Domain entities

| Entity | Responsibility |
| --- | --- |
| `experiments` | Frozen mandate, start/end, policy version, and lifecycle |
| `portfolios` | Base currency, capital, and experiment ownership |
| `assets` / `listings` | Stable instrument identity separated from exchange ticker |
| `decisions` | Append-only intent and reasoning |
| `decision_sources` | Point-in-time evidence and provenance |
| `model_runs` | Provider/model/configuration, prompts, outputs, and validation |
| `theses` | Original thesis and append-only revisions |
| `transactions` | Simulated executions and itemized costs |
| `cash_ledger` | Deposits, trades, fees, dividends, FX, and adjustments |
| `tax_lots` | Quantity and cost basis needed for realized P&L |
| `prices` / `fx_rates` | Time-stamped raw observations and provider metadata |
| `corporate_actions` | Splits, dividends, mergers, and symbol changes |
| `portfolio_snapshots` | Reproducible daily portfolio state |
| `benchmark_snapshots` | Reproducible counterfactual benchmark state |
| `calculation_runs` | Version and lineage for derived analytics |

## 7. Acceptance criteria by milestone

- **Portfolio engine:** invariant-driven unit tests cover buys, partial/full sells, fractional shares, fees, FX, dividends, splits, oversells, and insufficient cash.
- **Market data:** daily jobs are idempotent, freshness is visible, and missing/changed data enters an exception workflow.
- **Dashboard:** a reader can answer what is owned, why, and whether it beat the benchmark without documentation.
- **Decision system:** every trade has one prior sealed decision and historical records cannot be updated through application roles.
- **Analytics:** an independent calculation fixture matches returns, risk, cost drag, and attribution outputs.

## 8. Roadmap

Phase 0 freezes definitions. Phases 1–5 deliver the non-autonomous MVP. Phases 6–7 add structured model research and policy-constrained decisions. Phases 8–10 add committee workflows, automation, and the public experiment. A phase advances only after its milestone tests pass.

## 9. Open items intentionally deferred to Day Zero

- exact experiment start and end timestamps;
- AI provider, model version, and generation parameters;
- the initial candidate universe and portfolio;
- the initial market-condition/source snapshot;
- the commit containing the sealed Day Zero package.

These are not guessed during Phase 0 because they must reflect the operational system and information available immediately before the first decision.
