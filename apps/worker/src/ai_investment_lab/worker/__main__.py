"""Command-line entry point for scheduled and operator-triggered jobs."""

import argparse
import json
import os
import sys
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from ai_investment_lab.data_providers import EodhdClient, ProviderError
from ai_investment_lab.db.market_repository import MarketDataRepository
from ai_investment_lab.worker.service import (
    DailyJob,
    DailyOutcome,
    IngestionOutcome,
    MarketDataService,
    MissingMarketDataError,
)


def _date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("expected YYYY-MM-DD") from error


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-investment-lab-worker")
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser("search", help="look up an EODHD instrument")
    search.add_argument("query")
    search.add_argument("--exchange")
    search.add_argument("--type", dest="instrument_type")
    search.add_argument("--limit", type=int, default=20)

    calendar = subparsers.add_parser("calendar", help="cache a listing's exchange year")
    calendar.add_argument("listing_id", type=UUID)
    calendar.add_argument("--year", type=int, required=True)
    calendar.add_argument("--execution-key", default="manual")

    prices = subparsers.add_parser("prices", help="cache historical EOD prices")
    prices.add_argument("listing_id", type=UUID)
    prices.add_argument("--from", dest="date_from", type=_date, required=True)
    prices.add_argument("--to", dest="date_to", type=_date, required=True)
    prices.add_argument("--execution-key", default="manual")
    prices.add_argument("--refresh", action="store_true")

    daily = subparsers.add_parser("daily", help="ingest and value one completed UTC day")
    daily.add_argument(
        "--date",
        dest="valuation_date",
        type=_date,
        default=datetime.now(UTC).date() - timedelta(days=1),
    )
    daily.add_argument(
        "--execution-key",
        help="explicit key for an intentional restatement; defaults to the valuation date",
    )
    return parser


def _provider() -> EodhdClient:
    return EodhdClient(os.getenv("AIL_EODHD_API_TOKEN", ""))


def _database_url() -> str:
    return os.getenv(
        "AIL_DATABASE_URL",
        "postgresql+psycopg://ai_lab:ai_lab@localhost:5432/ai_investment_lab",
    )


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        provider = _provider()
        if args.command == "search":
            matches = provider.search(
                args.query,
                exchange=args.exchange,
                instrument_type=args.instrument_type,
                limit=args.limit,
            )
            print(json.dumps([asdict(item) for item in matches], default=str, indent=2))
            return 0

        engine = create_engine(_database_url(), pool_pre_ping=True)
        with Session(engine, expire_on_commit=False) as session:
            repository = MarketDataRepository(session)
            service = MarketDataService(repository, provider)
            outcome: IngestionOutcome | DailyOutcome
            try:
                if args.command == "calendar":
                    listing = repository.get_listing(args.listing_id)
                    outcome = service.ingest_calendar(
                        listing,
                        year=args.year,
                        execution_key=args.execution_key,
                    )
                elif args.command == "prices":
                    listing = repository.get_listing(args.listing_id)
                    for year in range(args.date_from.year, args.date_to.year + 1):
                        service.ingest_calendar(
                            listing,
                            year=year,
                            execution_key=args.execution_key,
                        )
                    outcome = service.ingest_prices(
                        listing,
                        date_from=args.date_from,
                        date_to=args.date_to,
                        execution_key=args.execution_key,
                        refresh=args.refresh,
                    )
                else:
                    outcome = DailyJob(repository, provider).run(
                        args.valuation_date,
                        execution_key=args.execution_key,
                    )
            except (ProviderError, MissingMarketDataError):
                session.commit()
                raise
            session.commit()
            print(json.dumps(asdict(outcome), default=str, indent=2))
        engine.dispose()
        return 0
    except (ProviderError, MissingMarketDataError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
