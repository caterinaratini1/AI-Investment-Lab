# ADR 0001: Phase 0 experimental baseline

- Status: Accepted for prelaunch
- Date: 2026-09-10
- Policy version: `0.1.0`

## Context

The experiment needs rules that exist before outcomes and implementation details can influence them. The project brief specifies EUR 10,000, a September 2026 start, an MSCI World comparison, public equities/UCITS ETFs/cash, and a 12-month initial duration, but leaves the executable benchmark, market-data source, costs, limits, and metric conventions open.

## Decision

1. Use the EUR Euronext Amsterdam listing of iShares Core MSCI World UCITS ETF USD (Acc), `IWDA` / `IE00B4L5Y983`, as the investable MSCI World proxy.
2. Use EODHD as the primary end-of-day market, corporate-action, reference, and FX data provider, subject to a public-display license review before launch.
3. Simulate at the first regular-session open strictly after a decision is sealed.
4. Charge each side `max(EUR 1.00, 0.10% of EUR notional)`, 0.05% adverse slippage, and 0.20% FX cost for non-EUR listings.
5. Use the concentration, liquidity, and turnover limits in the investment policy, with Day Zero construction reported separately and exempt from the ongoing turnover cap.
6. Make terminal net excess total return the primary metric and publish the predeclared risk-adjusted classification alongside it.
7. Keep the policy `prelaunch`; Day Zero-specific facts are sealed only after launch prerequisites pass.
8. Use benchmark-aware, long-only QARP as the initial investment style, normally targeting 8–15 holdings and 6–24 month holding periods.
9. Target Vercel for the Next.js frontend, Render for the FastAPI API and job processes, and Supabase for managed PostgreSQL and private evidence storage.

## Consequences

- The benchmark represents an attainable passive alternative but can differ from the official index through fees, tracking, tax, and market-price effects.
- EOD data makes execution reproducible but does not model intraday order behavior.
- The small-ticket minimum commission materially penalizes excessive trading, as a retail-sized portfolio would experience.
- A single provider simplifies provenance and deterministic reconciliation but creates provider dependency. Failures are surfaced rather than hidden behind an unspecified fallback.
- Keeping Day Zero unset makes Phase 0 complete without falsely implying that an operational experiment has already begun.

## Rejected alternatives

- **Direct MSCI index series:** less investable and potentially restricted for automated retrieval/redistribution.
- **A US-listed MSCI World ETF:** introduces avoidable benchmark trading-currency conversion and a less representative vehicle for a EUR-based experiment.
- **Unofficial scraped finance endpoints:** attractive for prototypes but weaker on contracts, metadata, corrections, and reproducibility.
- **Zero transaction costs:** materially rewards turnover and does not represent an executable comparison.
- **Same-day close execution:** can create lookahead unless decision cutoff and market availability are modeled perfectly.

## Launch follow-up

Before changing `status` to `active`, execute the Day Zero checklist in the methodology, validate that `IWDA` and all intended listings are covered by the subscribed provider plan, and record the exact commit and configuration hashes.
