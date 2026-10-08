"""Create an isolated test database in Compose Postgres, then run the requested check."""
import asyncio
import os
import subprocess
import sys
from urllib.parse import urlsplit, urlunsplit

import asyncpg


async def prepare_database():
    dsn = os.environ["TEST_DATABASE_URL"]
    parts = urlsplit(dsn)
    name = parts.path.lstrip("/")
    # Never permit the destructive pytest fixtures to use a service database.
    if name not in {"rh_test", "rh_smoke", "rh_quality"}:
        raise RuntimeError("Container checks require an isolated test/smoke/quality database")
    conn = await asyncpg.connect(urlunsplit(parts._replace(path="/postgres")))
    try:
        if not await conn.fetchval("SELECT 1 FROM pg_database WHERE datname=$1", name):
            await conn.execute(f'CREATE DATABASE "{name}"')
    finally:
        await conn.close()


def main():
    asyncio.run(prepare_database())
    mode = sys.argv[1] if len(sys.argv) > 1 else "pytest"
    if mode == "browser":
        module = os.environ["PLAYWRIGHT_MODULE"]
        subprocess.run(["node", "-e", "require(process.argv[1])", module], check=True)
        return subprocess.call(["node", "scripts/widget-e2e.cjs"])
    if mode == "quality":
        os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
        return subprocess.call([sys.executable, "-m", "scripts.quality", "--out", "/results/quality.json"])
    if mode == "smoke":
        # Fail rather than skip if browser tooling is unavailable in this image.
        subprocess.run(["node", "-e", "require(process.argv[1])", os.environ["PLAYWRIGHT_MODULE"]], check=True)
        args = ["tests/test_widget_browser.py", "-k", "real_openai", "-v"]
    else:
        args = sys.argv[2:] or ["-q"]
    return subprocess.call([sys.executable, "-m", "pytest", "--basetemp=/results/pytest", *args])


if __name__ == "__main__":
    raise SystemExit(main())
