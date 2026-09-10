import { afterEach, describe, expect, it, vi } from "vitest";

import { getDashboardData } from "./dashboard-data";

describe("getDashboardData", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("returns a clearly labelled deterministic preview when live IDs are absent", async () => {
    vi.stubEnv("AIL_WEB_PORTFOLIO_ID", "");

    const dashboard = await getDashboardData();

    expect(dashboard.mode).toBe("preview");
    expect(dashboard.notice).toContain("Illustrative pre-launch data");
    expect(dashboard.series).toHaveLength(8);
  });

  it("fails closed instead of substituting demo values when live data is unavailable", async () => {
    vi.stubEnv("AIL_WEB_API_BASE_URL", "http://api.test/api/v1");
    vi.stubEnv("AIL_WEB_PORTFOLIO_ID", "portfolio-id");
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("network unavailable"));

    const dashboard = await getDashboardData();

    expect(dashboard.mode).toBe("error");
    expect(dashboard.currentValue).toBeNull();
    expect(dashboard.holdings).toEqual([]);
    expect(dashboard.errorMessage).toBe("network unavailable");
  });

  it("selects latest revisions and builds the live benchmark comparison", async () => {
    vi.stubEnv("AIL_WEB_API_BASE_URL", "http://api.test/api/v1");
    vi.stubEnv("AIL_WEB_PORTFOLIO_ID", "portfolio-id");
    vi.stubEnv("AIL_WEB_BENCHMARK_LISTING_ID", "benchmark-id");

    const snapshot = (date: string, revision: number, totalValue: string) => ({
      id: `${date}-${revision}`,
      portfolio_id: "portfolio-id",
      valuation_date: date,
      cash_balance: "1000.00",
      positions_value: revision === 2 ? "9500.00" : "9000.00",
      total_value: totalValue,
      realized_pnl: "50.00",
      unrealized_pnl: revision === 2 ? "450.00" : "0.00",
      total_return: revision === 2 ? "0.050000" : "0.000000",
      calculation_version: "snapshot-v1",
      input_fingerprint: `fingerprint-${revision}`,
      revision,
      supersedes_id: null,
      created_at: "2026-09-10T06:00:00Z",
      positions:
        date === "2026-09-10" && revision === 2
          ? [
              {
                asset_id: "asset-id",
                listing_id: "listing-id",
                quantity: "10.00000000",
                cost_basis: "9000.00",
                price: "950.00000000",
                fx_rate_to_base: "1.000000000000",
                market_value: "9500.00",
                unrealized_pnl: "500.00",
                price_date: "2026-09-10",
                stale_days: 0,
                valuation_status: "CURRENT",
              },
            ]
          : [],
    });

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      let payload: unknown;
      if (url.endsWith("/portfolios/portfolio-id")) {
        payload = {
          id: "portfolio-id",
          name: "Live portfolio",
          base_currency: "EUR",
          starting_capital: "10000.00",
          cash_balance: "1000.00",
          realized_pnl: "50.00",
          policy_version: "1.0.0",
          version: 1,
          created_at: "2026-09-01T00:00:00Z",
          updated_at: "2026-09-10T00:00:00Z",
        };
      } else if (url.includes("/snapshots")) {
        payload = [
          snapshot("2026-09-03", 1, "10000.00"),
          snapshot("2026-09-10", 1, "10000.00"),
          snapshot("2026-09-10", 2, "10500.00"),
        ];
      } else if (url.includes("/assets/asset-id")) {
        payload = {
          id: "asset-id",
          listing_id: "listing-id",
          name: "Example Asset",
          ticker: "EXM",
          isin: "IE00B4L5Y983",
          exchange_mic: "XAMS",
          currency: "EUR",
          asset_type: "PUBLIC_EQUITY",
          sector: "Technology",
          provider: "EODHD",
          provider_symbol: "EXM.AS",
          provider_exchange_code: "AS",
          exchange_timezone: "Europe/Amsterdam",
          created_at: "2026-09-01T00:00:00Z",
        };
      } else if (url.includes("/listings/benchmark-id/prices")) {
        payload = [
          { observation_date: "2026-09-03", adjusted_close: "100.00", revision: 1 },
          { observation_date: "2026-09-10", adjusted_close: "108.00", revision: 1 },
          { observation_date: "2026-09-10", adjusted_close: "110.00", revision: 2 },
        ];
      } else if (url.includes("/market-data/issues")) {
        payload = [];
      } else {
        return new Response(null, { status: 404 });
      }
      return new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    });

    const dashboard = await getDashboardData();

    expect(dashboard.mode).toBe("live");
    expect(dashboard.currentValue).toBe(10_500);
    expect(dashboard.benchmarkReturn).toBeCloseTo(0.1);
    expect(dashboard.excessReturn).toBeCloseTo(-0.05);
    expect(dashboard.latestRevision).toBe(2);
    expect(dashboard.holdings[0]?.name).toBe("Example Asset");
  });
});
