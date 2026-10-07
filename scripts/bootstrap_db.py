"""Apply DDL and verify schemas."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import get_settings
from sqlalchemy import text
from src.utils.db import get_engine, run_ddl

get_settings.cache_clear()
engine = get_engine()
print("URL:", get_settings().db.sqlalchemy_url)
run_ddl(engine)
print("DDL OK")
with engine.connect() as conn:
    rows = conn.execute(
        text(
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name IN ('raw','staging','warehouse','analytics','audit','monitoring') "
            "ORDER BY 1"
        )
    ).fetchall()
    print("Schemas:", [r[0] for r in rows])
