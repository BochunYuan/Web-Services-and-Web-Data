#!/usr/bin/env python3
"""
Compatibility wrapper for the old Django import command.

The API now has one business/data implementation: FastAPI + SQLAlchemy +
Alembic. Django remains a WSGI deployment adapter, so data import delegates to
the shared importer instead of maintaining a second Django ORM loader.
"""

from __future__ import annotations

import asyncio
import sys

from scripts.import_data import main, verify


if __name__ == "__main__":
    if "--verify" in sys.argv:
        asyncio.run(verify())
    else:
        asyncio.run(main(reset="--reset" in sys.argv))
