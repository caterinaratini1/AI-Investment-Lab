export type DashboardMode = "preview" | "live" | "empty" | "error";

export type SeriesPoint = {
  date: string;
  label: string;
  portfolioValue: number;
  benchmarkValue: number | null;
};

export type DashboardHolding = {
  assetId: string;
  name: string;
  ticker: string;
  sector: string | null;
  currency: string;
  quantity: number;
  averageCost: number;
  price: number;
  localMarketValue: number;
  marketValue: number;
  weight: number;
  unrealizedPnl: number;
  returnRate: number;
  priceDate: string;
  staleDays: number;
  valuationStatus: string;
};

export type DashboardIssue = {
  id: string;
  type: string;
  detail: string;
  observationDate: string;
};

export type DashboardData = {
  mode: DashboardMode;
  notice: string;
  portfolioName: string;
  policyVersion: string;
  asOfDate: string | null;
  currency: string;
  startingCapital: number;
  currentValue: number | null;
  totalReturn: number | null;
  benchmarkReturn: number | null;
  excessReturn: number | null;
  dailyChange: number | null;
  dailyChangeRate: number | null;
  cashBalance: number | null;
  cashWeight: number | null;
  positionsValue: number | null;
  realizedPnl: number | null;
  unrealizedPnl: number | null;
  calculationVersion: string | null;
  latestRevision: number | null;
  benchmarkLabel: string;
  benchmarkMethod: string;
  series: SeriesPoint[];
  holdings: DashboardHolding[];
  issues: DashboardIssue[];
  errorMessage?: string;
};
