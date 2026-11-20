"""
OCR the SBP statistical PDFs into plain-text files.

The PDFs' embedded text layer is damaged (decimal points / thousands separators detached from digits), so each
page is rendered to an image and read with OCR. Default engine: RapidOCR (CPU, multi-process) - it reads minus
signs correctly. Optional ``--engine easyocr`` uses the NVIDIA GPU, but in testing it dropped minus signs
(-2,125,197 became 22,125,197) and was slower, so it is NOT recommended for numeric tables.
Layout is kept: boxes are grouped into rows and columns (same whitespace-channel method as
sbp_pdf_to_excel.py) and written tab-separated, one line per table row, with '=== Page n ===' headers.
Low-confidence cells (< 0.80) are marked with a trailing '?' and counted in the file footer.
PDFs are untrusted inputs: they are only rendered, never executed.

Usage: python -I scripts/sbp_pdf_to_text.py <pdf_dir> <out_dir> [--only NAME ...] [--dpi 220] [--cpu]
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sbp_pdf_to_excel import LOW_CONF, build_grid, split_merged_numeric_columns  # noqa: E402


def read_page(reader, page, dpi: int):
    pix = page.get_pixmap(dpi=dpi)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:
        img = img[:, :, :3]
    results = reader.readtext(img, detail=1, paragraph=False, batch_size=8, canvas_size=max(pix.width, pix.height))
    boxes = []
    for pts, text, conf in results:
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        boxes.append({"x0": min(xs), "y0": min(ys), "x1": max(xs), "y1": max(ys),
                      "text": text.strip(), "conf": float(conf)})
    return boxes


def read_page_rapid(engine, page, dpi: int):
    pix = page.get_pixmap(dpi=dpi)
    res, _ = engine(pix.tobytes("png"))
    boxes = []
    for pts, text, conf in res or []:
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        boxes.append({"x0": min(xs), "y0": min(ys), "x1": max(xs), "y1": max(ys),
                      "text": text.strip(), "conf": float(conf)})
    return boxes


def page_text(boxes):
    grid, confs = split_merged_numeric_columns(*build_grid(boxes))
    lines, low = [], 0
    for row, cf in zip(grid, confs):
        cells = []
        for c, q in zip(row, cf):
            if c is None:
                cells.append("")
            else:
                if q is not None and q < LOW_CONF:
                    c, low = c + "?", low + 1
                cells.append(c)
        lines.append("\t".join(cells).rstrip("\t"))
    return "\n".join(lines), low, len(grid)


def convert(reader, pdf: Path, out: Path, dpi: int, engine: str = "rapid") -> dict:
    doc = pymupdf.open(pdf)
    parts, low_total, rows_total = [], 0, 0
    t0 = time.perf_counter()
    for pno, page in enumerate(doc, 1):
        boxes = read_page_rapid(reader, page, dpi) if engine == "rapid" else read_page(reader, page, dpi)
        text, low, n = page_text(boxes)
        parts.append(f"=== Page {pno} ===\n{text}\n")
        low_total += low
        rows_total += n
    footer = (f"\n--- source: {pdf.name} | pages: {len(doc)} | rows: {rows_total} | low-confidence cells "
              f"(marked '?'): {low_total} | OCR: {'RapidOCR' if engine == 'rapid' else 'EasyOCR'} {dpi} dpi | "
              f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} ---\n"
              "--- Machine-read from a PDF image; verify critical figures against the source PDF. ---\n")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(parts) + footer, encoding="utf-8")
    return {"pdf": pdf.name, "pages": len(doc), "rows": rows_total, "low": low_total,
            "sec": round(time.perf_counter() - t0, 1)}


def _job(args):
    pdf, out, dpi = args
    from rapidocr_onnxruntime import RapidOCR

    try:
        return convert(RapidOCR(), Path(pdf), Path(out), dpi, "rapid")
    except Exception as exc:
        return {"pdf": Path(pdf).name, "error": f"{type(exc).__name__}: {exc}"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf_dir", type=Path)
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--dpi", type=int, default=250)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--engine", choices=["rapid", "easyocr"], default="rapid")
    a = ap.parse_args(argv)
    pdfs = [p for p in sorted(a.pdf_dir.glob("*.pdf")) if not a.only or p.stem in a.only]
    if a.engine == "easyocr":
        import easyocr
        import torch

        gpu = torch.cuda.is_available()
        print(f"EasyOCR on {'GPU' if gpu else 'CPU'}", flush=True)
        reader = easyocr.Reader(["en"], gpu=gpu, verbose=False)
        results = (convert(reader, p, a.out_dir / f"{p.stem}.txt", a.dpi, "easyocr") for p in pdfs)
    else:
        from concurrent.futures import ProcessPoolExecutor

        ex = ProcessPoolExecutor(max_workers=a.workers)
        results = ex.map(_job, [(str(p), str(a.out_dir / f"{p.stem}.txt"), a.dpi) for p in pdfs])
    for r in results:
        if "error" in r:
            print(f"{r['pdf']:55} FAILED {r['error']}", flush=True)
        else:
            print(f"{r['pdf']:55} pages={r['pages']:<3} rows={r['rows']:<5} low_conf={r['low']:<4} {r['sec']}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
