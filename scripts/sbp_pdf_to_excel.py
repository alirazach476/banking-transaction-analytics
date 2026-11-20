"""
Convert State Bank of Pakistan statistical PDFs into Excel workbooks using OCR.

Why OCR: the SBP PDFs have a damaged text layer (decimal points / thousands separators are detached
from their digits, e.g. '1195 .' for 11.95), so embedded-text extraction gives wrong numbers. Each page is
rendered to an image and read with RapidOCR (ONNX, local, no network).

Table reconstruction:
  * OCR text boxes are grouped into rows by vertical position;
  * columns are found from the vertical white-space channels between boxes of multi-box rows;
  * each box is assigned to the column containing its centre; single-box rows (titles, notes) go to column A.
Numbers ('1,234.5', '(1,234)', '12.3%') become numeric cells. Wrapped labels appear as separate rows.
Every workbook has a '_source' sheet (provenance, method, page/row counts) and a '_low_conf' sheet listing
cells whose OCR confidence is below 0.80, so uncertain values can be checked against the PDF.
PDFs are untrusted inputs: they are only rendered, never executed.

Usage: python -I scripts/sbp_pdf_to_excel.py <pdf_dir> <out_dir> [--only NAME ...] [--workers 3] [--dpi 250]
"""

from __future__ import annotations

import argparse
import re
import statistics
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pymupdf
from openpyxl import Workbook

NUM = re.compile(r"^\(?[-−]?\$?\d[\d,]*\.?\d*\)?%?$")
LOW_CONF = 0.80


def coerce(cell):
    """Numeric-looking text -> int/float; everything else cleaned text."""
    if cell is None:
        return None
    s = " ".join(str(cell).split())
    if not s:
        return None
    t = s.replace("−", "-")
    if NUM.match(t):
        neg = (t.startswith("(") and t.endswith(")")) or t.lstrip("($").startswith("-")
        core = re.sub(r"[()$%,\-]", "", t)
        try:
            v = float(core)
        except ValueError:
            return s
        v = -v if neg else v
        return int(v) if "." not in core else v
    return s


def ocr_boxes(engine, page, dpi: int):
    """Return list of dict(x0,y0,x1,y1,text,conf) in pixel coordinates."""
    pix = page.get_pixmap(dpi=dpi)
    res, _ = engine(pix.tobytes("png"))
    out = []
    for box, text, conf in res or []:
        xs, ys = [p[0] for p in box], [p[1] for p in box]
        out.append({"x0": min(xs), "y0": min(ys), "x1": max(xs), "y1": max(ys),
                    "text": text.strip(), "conf": float(conf)})
    return out


def build_grid(boxes):
    """Group OCR boxes into rows and columns. Returns (rows, confs) as parallel 2-D lists."""
    boxes = [b for b in boxes if b["text"]]
    if not boxes:
        return [], []
    h = statistics.median(b["y1"] - b["y0"] for b in boxes)
    boxes.sort(key=lambda b: ((b["y0"] + b["y1"]) / 2, b["x0"]))
    rows, cur, cy = [], [], None
    for b in boxes:
        yc = (b["y0"] + b["y1"]) / 2
        if cy is None or abs(yc - cy) <= 0.6 * h:
            cur.append(b)
            cy = yc if cy is None else (cy * (len(cur) - 1) + yc) / len(cur)
        else:
            rows.append(cur)
            cur, cy = [b], yc
    if cur:
        rows.append(cur)
    for r in rows:
        r.sort(key=lambda b: b["x0"])

    # column channels: gaps in the union of x-intervals of boxes from multi-box rows
    ivs = sorted((b["x0"], b["x1"]) for r in rows if len(r) >= 2 for b in r)
    cuts, cover_end = [], None
    min_gap = 0.9 * h
    for x0, x1 in ivs:
        if cover_end is None:
            cover_end = x1
            continue
        if x0 - cover_end >= min_gap:
            cuts.append((cover_end + x0) / 2)
        cover_end = max(cover_end, x1)

    def col_of(b):
        xc = (b["x0"] + b["x1"]) / 2
        return sum(1 for c in cuts if xc > c)

    ncols = len(cuts) + 1
    grid, confs = [], []
    for r in rows:
        if len(r) == 1 and (r[0]["x1"] - r[0]["x0"]) > 0 and ncols > 1:
            cols = [r[0]["text"]] + [None] * (ncols - 1)
            cf = [r[0]["conf"]] + [None] * (ncols - 1)
        else:
            cols, cf = [None] * ncols, [None] * ncols
            for b in r:
                i = col_of(b)
                cols[i] = f"{cols[i]} {b['text']}" if cols[i] else b["text"]
                cf[i] = b["conf"] if cf[i] is None else min(cf[i], b["conf"])
        grid.append(cols)
        confs.append(cf)
    # drop all-empty columns
    keep = [i for i in range(ncols) if any(r[i] is not None for r in grid)]
    grid = [[r[i] for i in keep] for r in grid]
    confs = [[r[i] for i in keep] for r in confs]
    return grid, confs


TOKEN = re.compile(r"^\(?[-−]?\$?\d[\d,]*\.?\d*\)?%?$")


def split_merged_numeric_columns(grid, confs):
    """OCR sometimes returns two adjacent numbers as one box ('315,351 -164,862').
    For columns where most non-empty cells are such multi-number strings, split them into sub-columns
    (right-aligned, since numeric columns are right-aligned)."""
    if not grid:
        return grid, confs
    ncols = len(grid[0])
    plan = {}
    for c in range(ncols):
        toks = [(r[c].split() if isinstance(r[c], str) else []) for r in grid]
        multi = [t for t in toks if len(t) > 1 and all(TOKEN.match(x) for x in t)]
        nonempty = [t for t in toks if t]
        if multi and len(multi) >= 0.5 * len(nonempty):
            plan[c] = max(len(t) for t in multi)
    if not plan:
        return grid, confs
    new_g, new_c = [], []
    for r, cf in zip(grid, confs):
        row, crow = [], []
        for c in range(ncols):
            if c in plan:
                k = plan[c]
                t = r[c].split() if isinstance(r[c], str) else []
                if t and all(TOKEN.match(x) for x in t) and len(t) <= k:
                    parts = [None] * (k - len(t)) + t
                else:
                    parts = [r[c]] + [None] * (k - 1)
                row.extend(parts)
                crow.extend([cf[c] if p is not None else None for p in parts])
            else:
                row.append(r[c])
                crow.append(cf[c])
        new_g.append(row)
        new_c.append(crow)
    return new_g, new_c


def convert(pdf: Path, out: Path, dpi: int = 250) -> dict:
    from rapidocr_onnxruntime import RapidOCR

    engine = RapidOCR()
    doc = pymupdf.open(pdf)
    wb = Workbook()
    wb.remove(wb.active)
    low = []
    n_rows = n_cells = 0
    for pno, page in enumerate(doc, 1):
        grid, confs = split_merged_numeric_columns(*build_grid(ocr_boxes(engine, page, dpi)))
        ws = wb.create_sheet(f"page_{pno}"[:31])
        for ri, (row, cf) in enumerate(zip(grid, confs), 1):
            ws.append([coerce(c) for c in row])
            for ci, (c, q) in enumerate(zip(row, cf), 1):
                if c is not None:
                    n_cells += 1
                    if q is not None and q < LOW_CONF:
                        low.append((f"page_{pno}", ri, ci, c, round(q, 3)))
        n_rows += len(grid)
    src = wb.create_sheet("_source", 0)
    for line in [("source_pdf", pdf.name), ("pages", len(doc)), ("rows_extracted", n_rows),
                 ("cells_extracted", n_cells), ("low_confidence_cells", len(low)),
                 ("method", f"OCR (RapidOCR, {dpi} dpi) + whitespace-channel column detection"),
                 ("converted_at_utc", datetime.now(timezone.utc).isoformat(timespec="seconds")),
                 ("note", "Machine-read from a PDF image. Verify critical figures against the source PDF; "
                          "see _low_conf for uncertain cells. Wrapped labels appear as separate rows.")]:
        src.append(list(line))
    lc = wb.create_sheet("_low_conf", 1)
    lc.append(["sheet", "row", "col", "ocr_text", "confidence"])
    for r in low:
        lc.append(list(r))
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return {"pdf": pdf.name, "pages": len(doc), "rows": n_rows, "cells": n_cells, "low": len(low)}


def _job(args):
    pdf, out, dpi = args
    try:
        return convert(Path(pdf), Path(out), dpi)
    except Exception as exc:  # report, continue with other files
        return {"pdf": Path(pdf).name, "error": f"{type(exc).__name__}: {exc}"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf_dir", type=Path)
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--dpi", type=int, default=250)
    a = ap.parse_args(argv)
    jobs = [(str(p), str(a.out_dir / f"{p.stem}.xlsx"), a.dpi) for p in sorted(a.pdf_dir.glob("*.pdf"))
            if not a.only or p.stem in a.only]
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        for r in ex.map(_job, jobs):
            if "error" in r:
                print(f"{r['pdf']:55} FAILED {r['error']}")
            else:
                print(f"{r['pdf']:55} pages={r['pages']:<3} rows={r['rows']:<5} cells={r['cells']:<6} low_conf={r['low']}",
                      flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
