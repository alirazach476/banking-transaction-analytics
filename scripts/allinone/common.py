"""Shared helpers for the all-in-one analysis parts (read-only warehouse access, chart style, part output)."""
from __future__ import annotations

import json
import re
from pathlib import Path

import duckdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
IMG = ROOT / "docs" / "img"
PARTS = ROOT / "docs" / "_parts"
IMG.mkdir(parents=True, exist_ok=True)
PARTS.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"figure.dpi": 130, "axes.spines.top": False, "axes.spines.right": False})


def connect():
    return duckdb.connect(str(ROOT / "data" / "warehouse" / "novabank_data.duckdb"), read_only=True)


def sbp_lines(con, doc, page=None):
    w = f" and page={page}" if page else ""
    return con.execute(f"select page,row_no,raw_line,label,n_values,v1,v2,v3,v4,v5,v6,v7,v8,v9,v10,v11,v12 from sbp.rows_parsed where document='{doc}'{w} order by page,row_no").df()


def save(name: str, md: str, data: dict):
    (PARTS / f"{name}.md").write_text(md, encoding="utf-8")
    (PARTS / f"{name}.json").write_text(json.dumps(data, indent=1, default=str), encoding="utf-8")
