"""
Start an embedded PostgreSQL instance for local development when Docker
is unavailable. Data directory persists under .pgdata/

Usage:
    python scripts/start_embedded_postgres.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PGDATA = ROOT / ".pgdata" / "novabank"


def main() -> str:
    from embedded_postgres import get_server

    PGDATA.parent.mkdir(parents=True, exist_ok=True)
    # cleanup_mode=None keeps server running after this process exits
    server = get_server(PGDATA, cleanup_mode=None)
    server.ensure_pgdata_inited()
    server.ensure_postgres_running()
    uri = server.get_uri(database="postgres")
    print(f"Embedded PostgreSQL running")
    print(f"URI: {uri}")
    print(f"PGDATA: {PGDATA}")

    # Create novabank role + database if needed
    # URI typically: postgresql://postgres@/postgres?host=...
    import psycopg2

    conn = psycopg2.connect(uri)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_roles WHERE rolname = 'novabank'")
    if not cur.fetchone():
        cur.execute("CREATE ROLE novabank LOGIN PASSWORD 'novabank_dev_password' SUPERUSER")
        print("Created role novabank")
    cur.execute("SELECT 1 FROM pg_database WHERE datname = 'novabank'")
    if not cur.fetchone():
        cur.execute("CREATE DATABASE novabank OWNER novabank")
        print("Created database novabank")
    cur.close()
    conn.close()

    # Write connection hint for .env
    # Parse host from uri query
    from urllib.parse import urlparse, parse_qs

    parsed = urlparse(uri)
    qs = parse_qs(parsed.query)
    host = qs.get("host", [None])[0] or parsed.hostname or "localhost"
    port = parsed.port or 5432

    env_path = ROOT / ".env"
    lines = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()
    mapping = {
        "POSTGRES_HOST": host if not str(host).startswith("/") else host,
        "POSTGRES_PORT": str(port),
        "POSTGRES_DB": "novabank",
        "POSTGRES_USER": "novabank",
        "POSTGRES_PASSWORD": "novabank_dev_password",
    }
    # For unix socket style host paths, SQLAlchemy needs host as directory
    new_lines = []
    seen = set()
    for line in lines:
        if "=" in line and not line.strip().startswith("#"):
            key = line.split("=", 1)[0].strip()
            if key in mapping:
                new_lines.append(f"{key}={mapping[key]}")
                seen.add(key)
                continue
        new_lines.append(line)
    for k, v in mapping.items():
        if k not in seen:
            new_lines.append(f"{k}={v}")
    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    print(f"Updated {env_path}")
    print(f"Connect: host={host} port={port} db=novabank user=novabank")

    # Also write a small status file
    status = ROOT / ".pgdata" / "status.txt"
    status.write_text(f"uri={uri}\nhost={host}\nport={port}\n", encoding="utf-8")
    return uri


if __name__ == "__main__":
    main()
