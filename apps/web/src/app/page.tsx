const foundations = [
  ["Portfolio engine", "Exact-decimal BUY, SELL, cash, cost basis, and P&L accounting"],
  ["API", "FastAPI commands backed by a transactional PostgreSQL ledger"],
  ["Experiment", "EUR 10,000 versus the IWDA MSCI World proxy"],
] as const;

export default function Home() {
  return (
    <main>
      <section className="hero">
        <p className="eyebrow">AI Investment Lab</p>
        <h1>The accounting foundation is being built.</h1>
        <p className="lede">
          A prospective, auditable experiment testing whether an AI-managed paper portfolio can
          outperform a passive global-equity benchmark.
        </p>
        <div className="status"><span aria-hidden="true" /> Phase 1 · Portfolio engine</div>
      </section>

      <section className="grid" aria-label="Phase 1 foundations">
        {foundations.map(([title, detail]) => (
          <article key={title}>
            <p>{title}</p>
            <h2>{detail}</h2>
          </article>
        ))}
      </section>

      <footer>Paper investing only · Not financial advice</footer>
    </main>
  );
}
