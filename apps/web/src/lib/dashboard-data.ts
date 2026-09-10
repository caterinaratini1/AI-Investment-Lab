import type { components } from "@ai-investment-lab/api-client";

import { demoDashboardData } from "./demo-data";
import type {
  DashboardData,
  DashboardHolding,
  DashboardIssue,
  SeriesPoint,
} from "./dashboard-types";

type Portfolio = components["schemas"]["PortfolioResponse"];
type Snapshot = components["schemas"]["PortfolioSnapshotResponse"];
type SnapshotPosition = components["schemas"]["SnapshotPositionResponse"];
type Asset = components["schemas"]["AssetResponse"];
type Price = components["schemas"]["PriceObservationResponse"];
type Issue = components["schemas"]["DataQualityIssueResponse"];

const FETCH_TIMEOUT_MS = 8_000;

function numeric(value: string): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    throw new Error("The API returned a non-numeric financial value.");
  }
  return parsed;
}

function apiUrl(baseUrl: string, path: string, params?: Record<string, string>): URL {
  const base = baseUrl.endsWith("/") ? baseUrl : `${baseUrl}/`;
  const url = new URL(path.replace(/^\//, ""), base);
  for (const [name, value] of Object.entries(params ?? {})) {
    url.searchParams.set(name, value);
  }
  return url;
}

async function getJson<T>(url: URL): Promise<T> {
  const response = await fetch(url, {
    cache: "no-store",
    headers: { accept: "application/json" },
    signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
  });
  if (!response.ok) {
    throw new Error(`Dashboard API request failed (${response.status}).`);
  }
  return (await response.json()) as T;
}

function latestSnapshotRevisions(snapshots: Snapshot[]): Snapshot[] {
  const byDate = new Map<string, Snapshot>();
  for (const snapshot of snapshots) {
    const existing = byDate.get(snapshot.valuation_date);
    if (!existing || snapshot.revision > existing.revision) {
      byDate.set(snapshot.valuation_date, snapshot);
    }
  }
  return [...byDate.values()].sort((left, right) =>
    left.valuation_date.localeCompare(right.valuation_date),
  );
}

function latestPriceRevisions(prices: Price[]): Map<string, Price> {
  const byDate = new Map<string, Price>();
  for (const price of prices) {
    const existing = byDate.get(price.observation_date);
    if (!existing || price.revision > existing.revision) {
      byDate.set(price.observation_date, price);
    }
  }
  return byDate;
}

function shortDate(value: string): string {
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    timeZone: "UTC",
  }).format(new Date(`${value}T00:00:00Z`));
}

export function buildSeries(
  snapshots: Snapshot[],
  benchmarkPrices: Price[],
  startingCapital: number,
): SeriesPoint[] {
  const prices = latestPriceRevisions(benchmarkPrices);
  const firstMatchingPrice = snapshots
    .map((snapshot) => prices.get(snapshot.valuation_date))
    .find((price): price is Price => price !== undefined);
  const basePrice = firstMatchingPrice ? numeric(firstMatchingPrice.adjusted_close) : null;

  return snapshots.map((snapshot) => {
    const price = prices.get(snapshot.valuation_date);
    const benchmarkValue =
      price && basePrice
        ? startingCapital * (numeric(price.adjusted_close) / basePrice)
        : null;
    return {
      date: snapshot.valuation_date,
      label: shortDate(snapshot.valuation_date),
      portfolioValue: numeric(snapshot.total_value),
      benchmarkValue,
    };
  });
}

function holdingFrom(
  position: SnapshotPosition,
  asset: Asset | undefined,
  totalValue: number,
): DashboardHolding {
  const quantity = numeric(position.quantity);
  const costBasis = numeric(position.cost_basis);
  const marketValue = numeric(position.market_value);
  return {
    assetId: position.asset_id,
    name: asset?.name ?? "Unknown asset",
    ticker: asset?.ticker ?? position.asset_id.slice(0, 8),
    sector: asset?.sector ?? null,
    currency: asset?.currency ?? "—",
    quantity,
    averageCost: quantity ? costBasis / quantity : 0,
    price: numeric(position.price),
    localMarketValue: quantity * numeric(position.price),
    marketValue,
    weight: totalValue ? marketValue / totalValue : 0,
    unrealizedPnl: numeric(position.unrealized_pnl),
    returnRate: costBasis ? numeric(position.unrealized_pnl) / costBasis : 0,
    priceDate: position.price_date,
    staleDays: position.stale_days,
    valuationStatus: position.valuation_status,
  };
}

function emptyDashboard(portfolio: Portfolio): DashboardData {
  return {
    mode: "empty",
    notice: "The portfolio exists, but no daily valuation snapshot has been published yet.",
    portfolioName: portfolio.name,
    policyVersion: portfolio.policy_version,
    asOfDate: null,
    currency: portfolio.base_currency,
    startingCapital: numeric(portfolio.starting_capital),
    currentValue: null,
    totalReturn: null,
    benchmarkReturn: null,
    excessReturn: null,
    dailyChange: null,
    dailyChangeRate: null,
    cashBalance: numeric(portfolio.cash_balance),
    cashWeight: null,
    positionsValue: null,
    realizedPnl: numeric(portfolio.realized_pnl),
    unrealizedPnl: null,
    calculationVersion: null,
    latestRevision: null,
    benchmarkLabel: "IWDA",
    benchmarkMethod: "Awaiting the first common valuation date",
    series: [],
    holdings: [],
    issues: [],
  };
}

function errorDashboard(message: string): DashboardData {
  return {
    ...demoDashboardData,
    mode: "error",
    notice: "Live data is configured but unavailable. Illustrative values are intentionally hidden.",
    currentValue: null,
    totalReturn: null,
    benchmarkReturn: null,
    excessReturn: null,
    dailyChange: null,
    dailyChangeRate: null,
    cashBalance: null,
    cashWeight: null,
    positionsValue: null,
    realizedPnl: null,
    unrealizedPnl: null,
    calculationVersion: null,
    latestRevision: null,
    series: [],
    holdings: [],
    issues: [],
    errorMessage: message,
  };
}

export async function getDashboardData(): Promise<DashboardData> {
  const baseUrl = process.env.AIL_WEB_API_BASE_URL;
  const portfolioId = process.env.AIL_WEB_PORTFOLIO_ID;
  const benchmarkListingId = process.env.AIL_WEB_BENCHMARK_LISTING_ID;

  if (!baseUrl || !portfolioId) {
    return demoDashboardData;
  }

  try {
    const [portfolio, rawSnapshots, issues] = await Promise.all([
      getJson<Portfolio>(apiUrl(baseUrl, `portfolios/${portfolioId}`)),
      getJson<Snapshot[]>(apiUrl(baseUrl, `portfolios/${portfolioId}/snapshots`)),
      getJson<Issue[]>(apiUrl(baseUrl, "market-data/issues", { issue_status: "OPEN" })),
    ]);
    const snapshots = latestSnapshotRevisions(rawSnapshots);
    if (!snapshots.length) {
      return emptyDashboard(portfolio);
    }

    const latest = snapshots.at(-1);
    if (!latest) {
      return emptyDashboard(portfolio);
    }

    const assetIds = [...new Set(latest.positions.map((position) => position.asset_id))];
    const [assets, benchmarkPrices] = await Promise.all([
      Promise.all(
        assetIds.map((assetId) =>
          getJson<Asset>(apiUrl(baseUrl, `assets/${assetId}`)),
        ),
      ),
      benchmarkListingId
        ? getJson<Price[]>(
            apiUrl(baseUrl, `listings/${benchmarkListingId}/prices`, {
              date_from: snapshots[0].valuation_date,
              date_to: latest.valuation_date,
            }),
          )
        : Promise.resolve([]),
    ]);

    const assetById = new Map(assets.map((asset) => [asset.id, asset]));
    const startingCapital = numeric(portfolio.starting_capital);
    const currentValue = numeric(latest.total_value);
    const series = buildSeries(snapshots, benchmarkPrices, startingCapital);
    const previous = snapshots.at(-2);
    const previousValue = previous ? numeric(previous.total_value) : null;
    const lastBenchmarkValue = series.at(-1)?.benchmarkValue ?? null;
    const benchmarkReturn = lastBenchmarkValue
      ? lastBenchmarkValue / startingCapital - 1
      : null;
    const totalReturn = numeric(latest.total_return);

    return {
      mode: "live",
      notice: "Published from immutable daily snapshots. Values include modeled trading costs.",
      portfolioName: portfolio.name,
      policyVersion: portfolio.policy_version,
      asOfDate: latest.valuation_date,
      currency: portfolio.base_currency,
      startingCapital,
      currentValue,
      totalReturn,
      benchmarkReturn,
      excessReturn: benchmarkReturn === null ? null : totalReturn - benchmarkReturn,
      dailyChange: previousValue === null ? null : currentValue - previousValue,
      dailyChangeRate:
        previousValue === null || previousValue === 0
          ? null
          : currentValue / previousValue - 1,
      cashBalance: numeric(latest.cash_balance),
      cashWeight: currentValue ? numeric(latest.cash_balance) / currentValue : 0,
      positionsValue: numeric(latest.positions_value),
      realizedPnl: numeric(latest.realized_pnl),
      unrealizedPnl: numeric(latest.unrealized_pnl),
      calculationVersion: latest.calculation_version,
      latestRevision: latest.revision,
      benchmarkLabel: "IWDA",
      benchmarkMethod: benchmarkListingId
        ? "Adjusted close rebased to equal starting capital; indicative until benchmark ledger launch"
        : "Benchmark listing is not configured",
      series,
      holdings: latest.positions
        .map((position) => holdingFrom(position, assetById.get(position.asset_id), currentValue))
        .sort((left, right) => right.marketValue - left.marketValue),
      issues: issues.slice(0, 5).map(
        (issue): DashboardIssue => ({
          id: issue.id,
          type: issue.issue_type,
          detail: issue.detail,
          observationDate: issue.observation_date,
        }),
      ),
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown dashboard error.";
    return errorDashboard(message);
  }
}
