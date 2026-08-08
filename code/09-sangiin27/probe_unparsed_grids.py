#!/usr/bin/env python3
"""Dump sangiin27 raw_json table grids for normalize planning.

v1.1.0: focus on unparsed sources with compact row dumps
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW_JSON = ROOT / "data" / "sangiin27" / "raw_json"
OUT = Path(__file__).resolve().parent / "output"
OUT.mkdir(parents=True, exist_ok=True)

# Prefer helpers from normalize if importable
import sys
sys.path.insert(0, str(ROOT / "src"))
from soumu_election.normalize import matrix, compact  # noqa: E402


TARGETS = [
    "03-05", "03-09", "03-10", "03-12", "03-13",
    "01-01", "01-02", "03-01", "03-02",
    "03-15", "03-16",
]


def find(prefix: str) -> list[Path]:
    return sorted(p for p in RAW_JSON.glob("*.json") if p.name.startswith(prefix + "_"))


def dump_table(table: list[list], max_rows: int = 25, max_cols: int = 20) -> list[str]:
    lines = []
    for r, row in enumerate(table[:max_rows]):
        cells = []
        for c, v in enumerate(row[:max_cols]):
            if v is None or v == "":
                continue
            text = compact(v) if isinstance(v, str) else str(v)
            if len(text) > 24:
                text = text[:21] + "..."
            cells.append(f"{c}:{text}")
        if cells:
            lines.append(f"R{r:03d} " + " | ".join(cells))
    return lines


def main() -> int:
    lines: list[str] = []
    for prefix in TARGETS:
        files = find(prefix)
        if not files:
            # unclassified / age variants
            files = sorted(p for p in RAW_JSON.glob(f"{prefix}*.json"))
        if not files:
            lines.append(f"=== {prefix}: MISSING ===\n")
            continue
        path = files[0]
        doc = json.loads(path.read_text(encoding="utf-8"))
        lines.append("=" * 72)
        lines.append(f"{prefix}: {path.name}")
        lines.append(f"dataset={doc.get('dataset')} sheets={len(doc.get('sheets') or [])}")
        for sheet in (doc.get("sheets") or [])[:3]:
            table = matrix(doc, sheet)
            lines.append(f"--- sheet={sheet['name']} size={len(table)}x{max((len(r) for r in table), default=0)}")
            lines.extend(dump_table(table, 30 if prefix == "03-13" else 22, 22))
            lines.append("")
        # sample unclassified once
    unclassified = sorted(RAW_JSON.glob("unclassified_*.json"))[:1]
    if unclassified:
        path = unclassified[0]
        doc = json.loads(path.read_text(encoding="utf-8"))
        lines.append("=" * 72)
        lines.append(f"unclassified sample: {path.name}")
        for sheet in (doc.get("sheets") or [])[:2]:
            table = matrix(doc, sheet)
            lines.append(f"--- sheet={sheet['name']} size={len(table)}x{max((len(r) for r in table), default=0)}")
            lines.extend(dump_table(table, 25, 12))
            lines.append("")

    out = OUT / "20260808_unparsed_grids.txt"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out)
    print("\n".join(lines[:200]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
