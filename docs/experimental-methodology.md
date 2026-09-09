# Experimental methodology

## 1. Research question and hypotheses

The initial experiment asks whether a policy-constrained AI portfolio produces a higher EUR total return than a passive MSCI World proxy over 12 calendar months, after applying the same explicit trade-cost model.

- **Primary null (`H0`):** terminal net portfolio return is less than or equal to terminal net benchmark return.
- **Primary alternative (`H1`):** terminal net portfolio return is greater than terminal net benchmark return.

This single, non-randomized market path cannot establish general predictive skill. Its output is an auditable case study. Statistical alpha and confidence intervals are descriptive and must not be presented as proof when the sample is too short.

## 2. Timeline

Phase 0 specifies September 2026 as the planned start month. Day Zero occurs only after the accounting, market-data, decision, and snapshot systems pass their launch checks.

At Day Zero the project must append and commit:

- exact UTC start and intended end timestamps;
- policy/config checksum and code commit SHA;
- initial EUR 10,000 cash ledger entry;
- benchmark order and execution rule;
- model/provider/version and parameters;
- candidate universe and point-in-time source manifest;
- initial market-condition snapshot;
- each initial decision and thesis.

The experiment ends at the close of the benchmark's regular session on the first trading day on or after the 12-month anniversary. A premature stop remains visible and the reason is reported.

## 3. Counterfactual benchmark

The benchmark receives the same EUR 10,000 at the same start timestamp. It purchases the maximum affordable fractional quantity of `IWDA` on Euronext Amsterdam at the first eligible open and pays the same commission and slippage rules. No FX fee applies because that listing trades in EUR. Any residual cash remains benchmark cash. It then follows buy-and-hold; the accumulating share class internally reinvests fund income.

The benchmark is not rebalanced and receives no later cash flows. If the AI portfolio still holds cash, that is part of the manager's result rather than mirrored in the benchmark.

## 4. Point-in-time and no-lookahead protocol

A decision has two states: `DRAFT` and `SEALED`. Drafts are operational working material and are not executable. Sealing creates canonical JSON, stores a SHA-256 hash, and prevents update/delete through application roles.

Every supplied fact records:

- source URI/provider and document identifier;
- retrieval timestamp;
- publication/observation timestamp when known;
- the exact payload or content-addressed private archive reference;
- parser/version and checksum.

A fact is eligible only if its publication or first-availability timestamp is no later than the decision's sealing timestamp. Unknown timing is flagged and cannot support a trade-critical claim without review.

Execution always occurs at the first regular-session open after sealing. This prevents use of a closing price that was not knowable when the decision was made. Historical decisions, source sets, and outputs are never regenerated with a newer model and passed off as originals.

## 5. Accounting

All quantities, money, prices, and FX rates use fixed-precision decimals. Values are stored in native currency and EUR.

### Daily valuation

For valuation date `t`:

`portfolio_value_t = EUR_cash_t + Σ(quantity_i,t × raw_close_i,t × EUR_FX_i,t)`

The system carries the last valid close across an exchange holiday for cross-market aggregation and marks it stale with its original observation date. It does not carry across a missing-data error until reviewed. Daily reporting uses a fixed 23:59:59 UTC cut so all eligible market closes for that UTC date can be included.

Raw tradable prices plus explicit splits and cash distributions drive the ledger. Provider-adjusted close may be retained for reconciliation but must not be combined with separately credited dividends.

### FX convention

`EUR_FX_i,t` is EUR received per one unit of the instrument's currency using the provider's daily close for that date. Trade notional uses the latest FX observation available at the simulated execution time; valuation uses that reporting date's close. Missing FX follows the same holiday/error distinction as prices.

### Cost basis and realized P&L

The portfolio uses moving weighted-average cost per asset in EUR, inclusive of BUY commission, slippage, and FX fee. A partial sale removes the proportional average cost. SELL commission and FX fee reduce realized proceeds.

`realized_P&L = net_EUR_sale_proceeds − EUR_cost_basis_removed`

Unrealized P&L is current EUR market value minus remaining EUR cost basis. Total P&L reconciles beginning capital, ending value, and any external cash flows (none are permitted after launch).

## 6. Returns and risk metrics

Let `V_t` be end-of-day value and `r_t = V_t / V_(t-1) − 1`. With no external flows, time-weighted and simple portfolio returns coincide.

| Metric | Definition |
| --- | --- |
| Total return | `V_end / V_start − 1` |
| Excess total return | portfolio total return minus benchmark total return |
| Cumulative return | cumulative product of `(1 + r_t)` minus 1 |
| Annualized volatility | sample standard deviation of daily returns × `sqrt(252)` |
| Downside volatility | root mean square of returns below the daily minimum acceptable return, annualized by `sqrt(252)` |
| Maximum drawdown | minimum of `V_t / running_max(V)_t − 1` |
| Sharpe ratio | annualized mean daily excess return over daily EUR risk-free rate divided by annualized volatility |
| Sortino ratio | annualized mean daily excess return over a 0% minimum acceptable return divided by annualized downside volatility |
| Information ratio | annualized mean daily active return divided by annualized tracking error |
| Beta | covariance of portfolio and benchmark daily returns divided by benchmark variance |
| Jensen alpha | annualized intercept from daily portfolio excess return regressed on benchmark excess return |

The EUR risk-free series is the ECB euro short-term rate (€STR), converted from annual percentage rate to a daily rate on an ACT/360 basis. If unavailable, affected Sharpe/alpha values are marked unavailable rather than silently using zero. Annualized metrics remain labeled provisional until at least 60 paired return observations exist.

## 7. Decision and behavior metrics

- **Closed-position win rate:** closed positions with positive realized total P&L divided by all closed positions. Partial exits do not count as separate wins.
- **Average winner/loser:** mean realized total return of winning/losing closed positions.
- **Holding period:** calendar days from first BUY execution to final SELL; weighted average for partial lots is also reported.
- **Contribution:** daily beginning weight multiplied by asset EUR return, reconciled with cash, FX, costs, and residuals.
- **Confidence analysis:** results grouped by the confidence sealed before entry; later confidence revisions form a separate time-series view.
- **Gross turnover:** absolute buy and sell notional divided by average portfolio value. Day Zero construction is disclosed separately and excluded from the ongoing policy limit.
- **Cost drag:** counterfactual portfolio value using identical gross executions with modeled commissions, slippage, and FX fees set to zero, minus actual value.

Sector and thesis analyses must publish coverage and classification rules. Metrics with fewer than five completed observations are shown but explicitly marked low-sample.

## 8. Predeclared interpretation

The headline answers are deliberately separate:

- **Return win:** net excess total return is greater than zero at the scheduled end.
- **Risk-adjusted win:** return win, portfolio Sharpe is greater than benchmark Sharpe, and portfolio maximum drawdown is no more than 5 percentage points worse than the benchmark.
- **Engineering success:** the system remains reproducible, auditable, tested, and publicly understandable, regardless of returns.

All metrics are published, not only favorable ones. The report must highlight universe changes, data gaps, policy amendments, manual interventions, model changes, and any departure from the original protocol.

## 9. Recalculation and corrections

Derived metrics may be recalculated when code improves, but each calculation run records code SHA, input snapshot IDs, policy version, and timestamp. Restated public figures retain the former value and state the reason. Source corrections from a provider are ingested as new versions; they never mutate the decision-time evidence archive.
