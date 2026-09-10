import type { CSSProperties } from "react";
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  CheckCircle2,
  Database,
  FileClock,
  ShieldCheck,
  WalletCards,
} from "lucide-react";

import type { DashboardData } from "../lib/dashboard-types";
import {
  formatDate,
  formatMoney,
  formatPercent,
  formatPoints,
  formatQuantity,
} from "../lib/formatters";
import { PerformanceChart } from "./performance-chart";

type DashboardViewProps = { data: DashboardData };

type MetricProps = {
  label: string;
  value: string;
  detail: string;
  tone?: "positive" | "negative" | "neutral";
  featured?: boolean;
};

function toneFor(value: number | null): "positive" | "negative" | "neutral" {
  if (value === null || value === 0) return "neutral";
  return value > 0 ? "positive" : "negative";
}

function Metric({ label, value, detail, tone = "neutral", featured = false }: MetricProps) {
  return (
    <article className={`metric-card${featured ? " featured" : ""}`}>
      <p>{label}</p>
      <strong className={tone}>{value}</strong>
      <span>{detail}</span>
    </article>
  );
}

function pnlBarStyle(value: number | null, largest: number): CSSProperties {
  const width = value === null || largest === 0 ? 0 : (Math.abs(value) / largest) * 100;
  return { width: `${Math.max(width, value === 0 ? 0 : 3)}%` };
}

export function DashboardView({ data }: DashboardViewProps) {
  const isPreview = data.mode === "preview";
  const isError = data.mode === "error";
  const hasValues = data.currentValue !== null;
  const pnlLargest = Math.max(
    Math.abs(data.realizedPnl ?? 0),
    Math.abs(data.unrealizedPnl ?? 0),
  );

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to portfolio dashboard</a>
      <header className="site-header">
        <a className="brand" href="#overview" aria-label="AI Investment Lab home">
          <span className="brand-mark" aria-hidden="true">AI</span>
          <span>Investment Lab</span>
        </a>
        <nav aria-label="Primary navigation">
          <a className="active" href="#overview">Overview</a>
          <a href="#performance">Performance</a>
          <a href="#portfolio">Portfolio</a>
          <a href="#methodology">Methodology</a>
        </nav>
        <span className={`experiment-state ${data.mode}`}>
          <i aria-hidden="true" />
          {data.mode === "live" ? "Published" : data.mode === "error" ? "Data error" : "Pre-launch"}
        </span>
      </header>

      <main id="main-content">
        <section className="page-heading" id="overview">
          <div>
            <p className="eyebrow">Portfolio 01 · {data.currency} · Fictional capital</p>
            <h1 aria-label="AI versus the world.">AI versus<br />the world.</h1>
          </div>
          <div className="as-of">
            <span>{isPreview ? "Illustrative preview" : data.mode === "live" ? "Latest valuation" : "Portfolio status"}</span>
            <time dateTime={data.asOfDate ?? undefined}>{formatDate(data.asOfDate)}</time>
            {data.calculationVersion ? <small>Calculation {data.calculationVersion} · revision {data.latestRevision}</small> : null}
          </div>
        </section>

        <div className={`notice ${isError ? "error" : ""}`} role={isError ? "alert" : "status"}>
          {isError ? <AlertTriangle aria-hidden="true" /> : <ShieldCheck aria-hidden="true" />}
          <div>
            <strong>{isError ? "Live publication unavailable" : isPreview ? "Preview mode" : data.mode === "empty" ? "Awaiting valuation" : "Audited snapshot"}</strong>
            <span>{data.notice}</span>
            {data.errorMessage ? <code>{data.errorMessage}</code> : null}
          </div>
        </div>

        <section className="metric-grid" aria-label="Portfolio summary">
          <Metric
            featured
            label="Portfolio value"
            value={formatMoney(data.currentValue, data.currency)}
            detail={hasValues ? `${formatPercent(data.totalReturn)} since inception` : "Not yet available"}
            tone={toneFor(data.totalReturn)}
          />
          <Metric
            label="Daily change"
            value={formatMoney(data.dailyChange, data.currency)}
            detail={formatPercent(data.dailyChangeRate)}
            tone={toneFor(data.dailyChange)}
          />
          <Metric
            label={`${data.benchmarkLabel} benchmark`}
            value={formatPercent(data.benchmarkReturn)}
            detail="Since common start"
            tone={toneFor(data.benchmarkReturn)}
          />
          <Metric
            label="Excess return"
            value={formatPoints(data.excessReturn)}
            detail={`vs ${data.benchmarkLabel}`}
            tone={toneFor(data.excessReturn)}
          />
          <Metric
            label="Cash"
            value={formatMoney(data.cashBalance, data.currency)}
            detail={`${formatPercent(data.cashWeight, 2, false)} of portfolio`}
          />
        </section>

        <section className="performance-card" id="performance" aria-labelledby="comparison-title">
          <div className="card-heading">
            <div>
              <p className="section-kicker">Primary experiment</p>
              <h2 id="comparison-title">{formatMoney(data.startingCapital, data.currency)} invested with AI vs {data.benchmarkLabel}</h2>
              <p className="card-description">Daily end-of-day value in {data.currency}. Portfolio results include modeled costs.</p>
            </div>
            <div className="legend" aria-label="Chart legend">
              <span><i className="portfolio-dot" /> AI portfolio</span>
              <span><i className="benchmark-dot" /> {data.benchmarkLabel}</span>
            </div>
          </div>
          <PerformanceChart
            series={data.series}
            currency={data.currency}
            benchmarkLabel={data.benchmarkLabel}
          />
          <p className="method-note"><Database aria-hidden="true" /> {data.benchmarkMethod}</p>
        </section>

        <div className="two-column-row">
          <section className="panel" aria-labelledby="pnl-title">
            <div className="card-heading compact">
              <div>
                <p className="section-kicker">Profit and loss</p>
                <h2 id="pnl-title">What drives the result</h2>
              </div>
              <WalletCards aria-hidden="true" />
            </div>
            <div className="pnl-list">
              {[
                ["Realized", data.realizedPnl],
                ["Unrealized", data.unrealizedPnl],
              ].map(([label, rawValue]) => {
                const value = rawValue as number | null;
                return (
                  <div className="pnl-row" key={label as string}>
                    <div><span>{label}</span><strong className={toneFor(value)}>{formatMoney(value, data.currency)}</strong></div>
                    <div
                      className="pnl-track"
                      role="img"
                      aria-label={`${label} profit and loss: ${formatMoney(value, data.currency)}`}
                    >
                      <i className={toneFor(value)} style={pnlBarStyle(value, pnlLargest)} />
                    </div>
                  </div>
                );
              })}
            </div>
            <p className="panel-footnote">Realized and unrealized P&amp;L are sourced from the latest immutable snapshot.</p>
          </section>

          <section className="panel" aria-labelledby="risk-title">
            <div className="card-heading compact">
              <div>
                <p className="section-kicker">Performance metrics</p>
                <h2 id="risk-title">Risk, without false precision</h2>
              </div>
              <ShieldCheck aria-hidden="true" />
            </div>
            <dl className="metric-list">
              <div><dt>Net total return</dt><dd>{formatPercent(data.totalReturn)}</dd></div>
              <div><dt>Invested capital</dt><dd>{formatMoney(data.positionsValue, data.currency)}</dd></div>
              <div><dt>Maximum drawdown</dt><dd className="pending">Phase 5</dd></div>
              <div><dt>Sharpe ratio</dt><dd className="pending">Phase 5</dd></div>
            </dl>
            <p className="panel-footnote">Risk statistics remain unpublished until the versioned analytics engine is implemented.</p>
          </section>
        </div>

        <section className="holdings-card" id="portfolio" aria-labelledby="holdings-title">
          <div className="card-heading">
            <div>
              <p className="section-kicker">Current portfolio</p>
              <h2 id="holdings-title">Holdings</h2>
              <p className="card-description">Latest stored close and snapshot FX rate. All portfolio values are shown in {data.currency}.</p>
            </div>
            <span className="record-count">{data.holdings.length} positions</span>
          </div>
          {data.holdings.length ? (
            <div className="table-scroll holdings-table">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Asset</th>
                    <th scope="col" className="numeric">Quantity</th>
                    <th scope="col" className="numeric">Avg cost</th>
                    <th scope="col" className="numeric">Last price</th>
                    <th scope="col" className="numeric">Value</th>
                    <th scope="col" className="numeric">Weight</th>
                    <th scope="col" className="numeric">Unrealized P&amp;L</th>
                    <th scope="col">Freshness</th>
                  </tr>
                </thead>
                <tbody>
                  {data.holdings.map((holding) => (
                    <tr key={holding.assetId}>
                      <th scope="row">
                        <span className="asset-name">{holding.name}</span>
                        <span className="asset-meta">{holding.ticker} · {holding.sector ?? "Unclassified"}</span>
                      </th>
                      <td className="numeric" data-label="Quantity">{formatQuantity(holding.quantity)}</td>
                      <td className="numeric" data-label="Avg cost">{formatMoney(holding.averageCost, holding.currency)}</td>
                      <td className="numeric" data-label="Last price">{formatMoney(holding.price, holding.currency)}</td>
                      <td className="numeric" data-label="Value">
                        {formatMoney(holding.marketValue, data.currency)}
                        {holding.currency !== data.currency ? (
                          <small>{formatMoney(holding.localMarketValue, holding.currency)} local</small>
                        ) : null}
                      </td>
                      <td className="numeric" data-label="Weight">{formatPercent(holding.weight, 1, false)}</td>
                      <td className={`numeric ${toneFor(holding.unrealizedPnl)}`} data-label="Unrealized P&amp;L">
                        {formatMoney(holding.unrealizedPnl, data.currency)}
                        <small>{formatPercent(holding.returnRate)}</small>
                      </td>
                      <td data-label="Freshness">
                        <span className={`freshness ${holding.staleDays > 0 ? "stale" : ""}`}>
                          {holding.staleDays > 0 ? <AlertTriangle aria-hidden="true" /> : <CheckCircle2 aria-hidden="true" />}
                          {holding.staleDays === 0 ? "Current" : `${holding.staleDays}d stale`}
                        </span>
                        <small>{formatDate(holding.priceDate, false)} · {holding.valuationStatus}</small>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="empty-state">
              <WalletCards aria-hidden="true" />
              <h3>No published holdings</h3>
              <p>Positions will appear with the first successful daily portfolio snapshot.</p>
            </div>
          )}
        </section>

        <div className="two-column-row" id="methodology">
          <section className="panel" aria-labelledby="integrity-title">
            <div className="card-heading compact">
              <div>
                <p className="section-kicker">Audit trail</p>
                <h2 id="integrity-title">Data integrity</h2>
              </div>
              <Database aria-hidden="true" />
            </div>
            {data.issues.length ? (
              <ul className="issue-list">
                {data.issues.map((issue) => (
                  <li key={issue.id}>
                    <AlertTriangle aria-hidden="true" />
                    <span><strong>{issue.type}</strong>{issue.detail}<small>{issue.observationDate}</small></span>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="integrity-ok">
                <CheckCircle2 aria-hidden="true" />
                <div><strong>No open data-quality issues</strong><span>{isPreview ? "Preview state only; no provider records were queried." : "The latest API quality queue is clear."}</span></div>
              </div>
            )}
          </section>

          <section className="panel" aria-labelledby="decisions-title">
            <div className="card-heading compact">
              <div>
                <p className="section-kicker">Decision history</p>
                <h2 id="decisions-title">Recorded before outcomes</h2>
              </div>
              <FileClock aria-hidden="true" />
            </div>
            <div className="phase-boundary">
              <span>Next capability</span>
              <strong>Immutable decision records arrive in Phase 4.</strong>
              <p>The dashboard will show the evidence, thesis, confidence, dissent, and timestamp behind each trade—never a hindsight rewrite.</p>
            </div>
          </section>
        </div>

        <section className="methodology-strip" aria-label="Experiment methodology summary">
          <div><span>01</span><strong>Same clock</strong><p>Portfolio and benchmark share capital, currency, and valuation dates.</p></div>
          <div><span>02</span><strong>Net results</strong><p>Commission, slippage, FX fees, and cash are part of performance.</p></div>
          <div><span>03</span><strong>Append, never rewrite</strong><p>Corrections create traceable revisions instead of replacing history.</p></div>
        </section>
      </main>

      <footer>
        <span>Fictional capital · End-of-day data · Not financial advice</span>
        <span className="footer-links">
          {data.totalReturn !== null && data.totalReturn >= 0 ? <ArrowUpRight aria-hidden="true" /> : <ArrowDownRight aria-hidden="true" />}
          {data.portfolioName} · policy {data.policyVersion}
        </span>
      </footer>
    </div>
  );
}
