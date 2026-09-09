# Investment policy

Policy version: `0.1.0` (prelaunch)  
Base currency: EUR  
Starting capital: EUR 10,000 fictional capital  
Initial horizon: 12 calendar months

The machine-readable counterpart is [`../config/experiment-policy.json`](../config/experiment-policy.json). If prose and configuration differ, trading must stop until a new policy version resolves the conflict.

## 1. Mandate

The portfolio may seek capital appreciation through long-only positions in liquid public equities and UCITS ETFs. It may hold cash. It must operate only as a paper portfolio and may not place real orders.

The manager evaluates each investment in the context of the whole portfolio. It is allowed to underperform, hold cash, and say HOLD. Its task is to follow a reproducible process, not to maximize activity.

The initial strategy is **benchmark-aware quality at a reasonable price (QARP)**. It seeks financially durable businesses or diversified UCITS ETFs whose expected return is attractive relative to valuation and risk. Equity analysis emphasizes balance-sheet resilience, durable competitive advantages, cash generation, sensible capital allocation, valuation, and a specific route by which mispricing may close or compounding may become visible. The normal intended holding period is 6–24 months.

The strategy is bottom-up rather than index-hugging: benchmark sector and country weights inform risk review but do not set portfolio weights. It does not use systematic market timing, price targets alone, or a mandatory trade schedule. The target is 8–15 holdings when enough qualifying ideas exist; this is a construction target, not permission to violate the hard 20-holding maximum or the minimum cash rule.

## 2. Eligible instruments

An instrument is eligible only when all of the following are true at decision time:

- it is a common/public equity or UCITS ETF admitted to trading on a supported regulated exchange;
- it can be uniquely identified by ISIN plus exchange MIC (ticker alone is insufficient);
- end-of-day raw prices and corporate-action data are available from the primary provider;
- the security has market capitalization of at least EUR 1 billion, unless it is a UCITS ETF;
- its 20-session median daily value traded is at least EUR 5 million;
- trading and valuation currency can be converted to EUR using an available FX series;
- it is not suspended and no unresolved instrument-identity or price-quality exception exists.

Fractional shares are permitted for accounting. Cash earns no interest in the MVP; this deliberately conservative rule may be changed only prospectively in a new experiment.

## 3. Prohibited activity

The portfolio may not use margin, leverage, short selling, CFDs, options, futures, swaps, cryptocurrency, private securities, leveraged/inverse ETFs, securities lending, or any instrument capable of creating loss beyond invested capital.

It may not deliberately trade on material non-public information, fabricate unavailable evidence, or use information published after a decision's sealing timestamp.

## 4. Portfolio constraints

All limits are tested using the latest valid EUR valuation available before a decision is sealed and again using the simulated execution price.

| Constraint | Limit |
| --- | ---: |
| Cash after a BUY | at least 5% of portfolio value |
| Single position immediately after a trade | at most 15% |
| GICS sector immediately after a trade | at most 30% |
| New position target weight | at least 2% |
| Concurrent non-cash holdings | at most 20 |
| Monthly gross turnover | at most 25% |

Gross turnover for a period is total absolute EUR purchase and sale notional divided by average portfolio value. Corporate actions and benchmark trades do not count as manager turnover.

Day Zero portfolio construction is reported separately and is exempt from the monthly turnover limit. The limit applies immediately after the initial portfolio is established.

A falling price or classification change may create a passive limit breach. This is recorded and reviewed; it does not cause an unlogged automatic trade. No new trade may increase an existing breach.

## 5. Decision requirements

Every BUY, SELL, and deliberate HOLD review must be sealed with:

- decision and target asset;
- target quantity, value, or post-trade weight;
- thesis and specific reason for acting now;
- expected holding-period range;
- confidence (`LOW`, `MEDIUM`, or `HIGH`) with a numeric probability only when it has a clearly defined event and horizon;
- expected upside with horizon and valuation basis;
- principal risks and observable invalidation conditions;
- source manifest and portfolio snapshot known at the time;
- author/model identity, version, parameters, and prompt/template version;
- policy checks and canonical record hash.

`HIGH` confidence does not allow larger positions than the concentration limits. A thesis change creates a new thesis revision; it never edits the original.

## 6. Execution convention

1. Seal the decision and its source manifest.
2. Select the first regular trading session whose open is strictly later than the sealed timestamp.
3. Use that session's raw official/provider opening price as the reference price.
4. Apply 0.05% adverse slippage: increase a BUY price or decrease a SELL price.
5. Convert local notional and costs using the recorded EUR FX rate defined in the methodology.
6. Charge commission of `max(EUR 1.00, 0.10% × EUR notional)`.
7. Charge an additional 0.20% of EUR notional when the listing currency is not EUR.
8. Re-run cash and limit checks. If they fail, reject the execution and append a rejection record; do not silently resize it.

Orders are simulated as immediately and fully filled at the modeled price. Limit orders, partial fills, intraday timing, and market impact are outside the MVP. Sell proceeds settle immediately for paper-accounting purposes.

## 7. Cash and distributions

- Buys debit gross notional plus all costs; sells credit gross proceeds less all costs.
- Cash must never be negative after a completed transaction.
- Cash dividends are credited on the provider's payment date when available, otherwise on ex-date with the fallback explicitly flagged.
- Dividends are recorded gross of investor-specific tax because no investor tax domicile is modeled.
- Splits change quantity and per-share cost but not total cost basis or portfolio value.
- Other corporate actions enter manual review until deterministic handling exists.

## 8. Exceptions and changes

Operational corrections are append-only records referencing the original. A policy amendment requires a new semantic version, rationale, approval time, and effective time. Amendments cannot change how earlier decisions are judged. Any material change after launch must be displayed in public reporting and results segmented when comparability is affected.
