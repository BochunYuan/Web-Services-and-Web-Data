from __future__ import annotations

import argparse
import json
import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def configure_django() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "f1_django.settings")

    import django
    from django.apps import apps

    if not apps.ready:
        django.setup()


@lru_cache(maxsize=1)
def get_django_settings():
    configure_django()

    from django.conf import settings

    return settings


@lru_cache(maxsize=1)
def get_openapi_schema() -> dict[str, Any]:
    # Django still serves /openapi.json in deployment, but the schema should be
    # generated from the single FastAPI implementation to avoid drift.
    from app.main import app

    return app.openapi()


def export_schema(output_path: Path | None = None) -> Path | None:
    schema = get_openapi_schema()
    payload = json.dumps(schema, indent=2, ensure_ascii=True) + "\n"

    if output_path is None:
        print(payload, end="")
        return None

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(payload, encoding="utf-8")
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export the OpenAPI schema generated from the FastAPI core used by Django.",
    )
    parser.add_argument(
        "--file",
        dest="output_file",
        type=Path,
        help="Optional output path. If omitted, writes the schema to stdout.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    written = export_schema(args.output_file)
    if written is not None:
        print(f"Wrote {written}")


if __name__ == "__main__":
    main()
