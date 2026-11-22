"""The DuckDB adapter that lets the analytics API run without PostgreSQL (hosted read-only demo). No database server needed."""
from __future__ import annotations

import datetime as dt

import duckdb
import pytest
from fastapi import HTTPException

from src.api.dash import common


@pytest.fixture()
def engine(tmp_path):
    path = tmp_path / "t.duckdb"
    con = duckdb.connect(str(path))
    con.execute("CREATE SCHEMA ui")
    con.execute("CREATE TABLE ui.t AS SELECT * FROM (VALUES (1, 'a', DATE '2025-01-05', 10.5), (2, 'b', DATE '2025-02-01', 20.0), (3, 'a', DATE '2025-03-09', NULL)) v(id, grp, d, amt)")
    con.close()
    return common._DuckEngine(str(path))


def run(engine, sql, **p):
    with engine.connect() as c:
        return c.execute(sql, p)


def test_named_parameters_and_cast_operator(engine):
    rows = run(engine, "SELECT id::int AS id, CAST(:lo AS date) AS lo FROM ui.t WHERE grp = :g AND d BETWEEN :lo AND :hi ORDER BY id", g="a", lo=dt.date(2025, 1, 1), hi=dt.date(2025, 12, 31))
    assert [r._mapping["id"] for r in rows] == [1, 3]
    assert rows.fetchall()[0]._mapping["lo"] == dt.date(2025, 1, 1)


def test_extra_parameters_are_ignored_like_sqlalchemy(engine):
    assert run(engine, "SELECT count(*) FROM ui.t WHERE grp = :g", g="a", unused=123, also=None).scalar() == 2


def test_time_literals_and_double_colons_are_not_parameters(engine):
    assert run(engine, "SELECT '12:30' AS t, 5::int AS n").fetchall()[0]._mapping == {"t": "12:30", "n": 5}


def test_rows_behave_like_tuples_and_mappings(engine):
    row = run(engine, "SELECT id, grp FROM ui.t WHERE id = :i", i=2).fetchall()[0]
    assert tuple(row) == (2, "b") and row._mapping == {"id": 2, "grp": "b"}


def test_filter_clause_and_percentile_work_on_duckdb(engine):
    r = run(engine, "SELECT count(*) FILTER (WHERE grp = 'a') AS a, percentile_cont(0.5) WITHIN GROUP (ORDER BY id) AS med FROM ui.t").fetchall()[0]._mapping
    assert r["a"] == 2 and r["med"] == 2


def test_demo_mode_refuses_writes_with_a_clear_message(monkeypatch):
    monkeypatch.setattr(common, "DEMO", True)
    with pytest.raises(HTTPException) as e:
        common.write("DELETE FROM ui.t")
    assert e.value.status_code == 403 and "read-only" in e.value.detail


def test_engine_is_read_only(engine, tmp_path):
    ro = common._DuckEngine(str(tmp_path / "t.duckdb"))
    with pytest.raises(Exception):
        run(ro, "INSERT INTO ui.t VALUES (9, 'z', DATE '2025-01-01', 1)")
