from pathlib import Path

replacements = {
    "\u2014": "-",
    "\u2013": "-",
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2026": "...",
    "\u00b7": "|",
}

for rel in [
    "web/index.html",
    "web/dashboard.html",
    "dashboards/novabank_bi_dashboard.html",
]:
    path = Path(rel)
    text = path.read_text(encoding="utf-8")
    for old, new in replacements.items():
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")
    print("updated", rel)
