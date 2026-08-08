#!/usr/bin/env python3
# Try reuse parse_smd on sangiin26 district xlsx
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from soumu_election.download import parse_smd  # noqa: E402

path = ROOT / "code" / "09-sangiin26" / "output" / "hokkaido_district.xlsx"
source = {"label": "北海道_選挙区", "url": "", "category": "district", "dataset": "test"}
rows = parse_smd(path, source, 26)
print("rows", len(rows))
print("sample", rows[:3])
print("types", {r.get("row_type") for r in rows})
units = [r for r in rows if r.get("row_type") == "reporting_unit"]
print("reporting_unit", len(units), units[0] if units else None)
