# Data and benchmark decisions

## 1. Benchmark: IWDA on Euronext Amsterdam

The conceptual benchmark is the MSCI World Index. The operational benchmark is the EUR listing of the **iShares Core MSCI World UCITS ETF USD (Acc)**:

| Field | Value |
| --- | --- |
| Ticker | `IWDA` |
| EODHD symbol | `IWDA.AS` |
| Exchange | Euronext Amsterdam |
| MIC | `XAMS` |
| Trading currency | EUR |
| ISIN | `IE00B4L5Y983` |
| Share class | Accumulating |
| Target index | MSCI World Index |

MSCI describes the index as large- and mid-cap exposure across developed markets covering roughly 85% of free-float-adjusted market capitalization in each country. iShares lists the same fund share class on Euronext Amsterdam as `IWDA` in EUR.

### Why use an investable proxy

- It produces a price series that a European paper investor could actually transact in.
- The EUR listing removes a separate benchmark FX trade while preserving the fund's underlying global currency exposure.
- The accumulating share class makes benchmark income part of its traded value.
- It avoids presenting a licensed index series as if it were freely redistributable.

### Accepted limitations

IWDA is not the index itself. Tracking difference, fund expenses, sampling, tax treatment, cash drag inside the fund, and market-price/NAV differences affect it. Those are part of the attainable passive alternative and are disclosed. If `IWDA` becomes unavailable, the original series is not spliced silently: a benchmark-change event and linked successor series are published.

Official references:

- [MSCI World Index overview](https://www.msci.com/indexes/index/990100/msci-world-index)
- [iShares Core MSCI World UCITS ETF fund page and listings](https://www.ishares.com/uk/individual/en/products/251882/ishares-msci-world-ucits-etf)

## 2. Primary market-data provider: EODHD

EODHD is selected for the MVP because one provider can supply worldwide end-of-day equities/ETF data, raw and adjusted prices, exchange metadata, corporate actions, and FX series. Its symbol and exchange metadata fit the project's requirement to distinguish an instrument from a particular listing.

Required feeds:

- exchange and symbol reference data;
- raw daily OHLCV for execution and valuation;
- adjusted close for reconciliation only;
- dividends and splits;
- daily FX rates into EUR;
- exchange trading hours/holidays when available.

Relevant provider documentation:

- [Historical end-of-day data](https://eodhd.com/lp/historical-eod-api)
- [Supported exchanges and ticker lists](https://eodhd.com/financial-apis/exchanges-api-list-of-tickers-and-trading-hours)
- [Bulk end-of-day prices, splits, and dividends](https://eodhd.com/financial-apis/bulk-api-eod-splits-dividends)
- [Plans and current limits](https://eodhd.com/pricing)

### Licensing rule

An API subscription is not permission to redistribute raw market data. Before any public deployment, the operator must confirm that the selected plan and each exchange permit the intended display. Raw responses, bulk exports, and credentials stay outside Git. The public application should publish derived portfolio results and only the minimum delayed observations allowed by the applicable license.

The free tier is suitable only for an integration spike. The planned portfolio requires the worldwide end-of-day feed or an equivalent commercial entitlement. Provider pricing and entitlements can change, so Phase 2 includes a go-live license check rather than treating a 2026 web page as permanent.

## 3. Secondary authoritative sources

- [ECB euro short-term rate (€STR)](https://www.ecb.europa.eu/stats/financial_markets_and_interest_rates/euro_short-term_rate/html/index.en.html) and its Data Portal history for risk-adjusted calculations.
- Issuer and exchange notices for ambiguous corporate actions.
- Instrument issuer documents for stable identity and UCITS status.

These sources do not become silent substitutes for missing prices. Every override creates a provenance record and a visible exception resolution.

## 4. Ingestion contract

Each observation stores provider, provider symbol, stable asset/listing IDs, exchange MIC, native currency, observation date/time, retrieval time, raw payload checksum, raw/adjusted flag, and ingestion-run ID.

Ingestion must be idempotent on provider + listing + interval + observation time + data version. A corrected upstream value creates a new version and marks the former record superseded.

Validation includes:

- duplicate and out-of-order observations;
- non-positive prices or FX rates;
- implausible one-session changes requiring corporate-action reconciliation;
- currency or exchange changes;
- missing expected sessions versus exchange calendar;
- stale carried values and cross-source reconciliation samples.

No fallback provider is selected in Phase 0. Adding one without deterministic precedence would weaken reproducibility. Phase 2 may adopt one through a new decision record that defines when it is used and how discrepancies are resolved.
