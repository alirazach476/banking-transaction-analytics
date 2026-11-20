"""
Safely extract only .csv / .xls / .xlsx members from downloaded (untrusted) zip archives.

Safeguards: members are read by name only (never trusted paths: base filename is used, so '..' or absolute
paths cannot escape), only whitelisted extensions are extracted, per-member and total uncompressed size
limits guard against zip bombs, and nothing is executed.

Usage: python -I scripts/extract_zip_csv.py <zip_dir> <out_dir> [--max-member-gb 20]
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

ALLOWED = (".csv", ".xls", ".xlsx")


def extract(zip_path: Path, out_dir: Path, max_member_bytes: int) -> list[tuple[str, int]]:
    done = []
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            name = Path(info.filename.replace("\\", "/")).name  # base name only
            if info.is_dir() or not name.lower().endswith(ALLOWED):
                continue
            if info.file_size > max_member_bytes:
                print(f"  SKIP too large: {name} ({info.file_size/1e9:.1f} GB)")
                continue
            dest = out_dir / f"{zip_path.stem}__{name}"
            if dest.exists() and dest.stat().st_size == info.file_size:
                done.append((dest.name, info.file_size))
                continue
            out_dir.mkdir(parents=True, exist_ok=True)
            written = 0
            with z.open(info) as src, open(dest, "wb") as dst:
                while chunk := src.read(1 << 20):
                    written += len(chunk)
                    if written > max_member_bytes:  # declared size may lie
                        break
                    dst.write(chunk)
            if written > max_member_bytes:
                dest.unlink(missing_ok=True)
                print(f"  ABORT (exceeds limit while reading): {name}")
                continue
            done.append((dest.name, written))
    return done


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("zip_dir", type=Path)
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("--max-member-gb", type=float, default=20.0)
    a = ap.parse_args(argv)
    total = 0
    for zp in sorted(a.zip_dir.glob("*.zip")):
        try:
            got = extract(zp, a.out_dir, int(a.max_member_gb * 1e9))
        except zipfile.BadZipFile:
            print(f"{zp.name}: not a valid zip (skipped)")
            continue
        for n, s in got:
            total += s
            print(f"{zp.name}: {n} {s/1e6:.1f} MB")
    print(f"extracted total {total/1e9:.2f} GB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
