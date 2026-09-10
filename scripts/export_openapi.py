"""Export FastAPI's canonical OpenAPI contract for generated clients."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "schemas" / "openapi.json"
PYTHON_SOURCE_ROOTS = (
    ROOT / "apps" / "api" / "src",
    ROOT / "apps" / "worker" / "src",
    ROOT / "packages" / "data_providers" / "src",
    ROOT / "packages" / "db" / "src",
    ROOT / "packages" / "domain" / "src",
)


def main() -> None:
    for source_root in PYTHON_SOURCE_ROOTS:
        sys.path.insert(0, str(source_root))

    from ai_investment_lab.api.main import create_app

    OUTPUT.write_text(
        json.dumps(create_app().openapi(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
