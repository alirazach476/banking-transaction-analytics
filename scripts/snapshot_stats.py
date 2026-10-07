"""Print analytics mart stats for documentation."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from config.settings import get_settings
from src.utils.db import get_engine

get_settings.cache_clear()
engine = get_engine()

with engine.connect() as c:
    cols = c.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='analytics' AND table_name='mart_channel_performance' "
            "ORDER BY ordinal_position"
        )
    ).fetchall()
    print("channel cols:", [x[0] for x in cols])

    segs = c.execute(
        text(
            "SELECT activity_segment, COUNT(*) AS n "
            "FROM analytics.mart_customer_activity GROUP BY 1 ORDER BY 2 DESC"
        )
    ).fetchall()
    print("SEGMENTS:")
    for s in segs:
        print(f"  {s[0]}: {s[1]}")

    ch = c.execute(text("SELECT * FROM analytics.mart_channel_performance LIMIT 1")).mappings().first()
    print("channel row keys:", list(ch.keys()) if ch else None)

    top_branch = c.execute(
        text(
            "SELECT * FROM analytics.mart_branch_performance "
            "ORDER BY transaction_count DESC NULLS LAST LIMIT 3"
        )
    ).mappings().fetchall()
    print("TOP BRANCHES:")
    for b in top_branch:
        print(dict(b))
