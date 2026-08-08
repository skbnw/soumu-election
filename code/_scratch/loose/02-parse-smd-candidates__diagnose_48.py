# v1.0: 第48回の当選2人/0人区の割当を診断
import sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from test_parse_03_13 import parse_kaiji

facts = parse_kaiji(48)
by = defaultdict(list)
for f in facts:
    by[(f["prefecture"], f["district_number"])].append(f)

for key in sorted(by):
    elected = [f for f in by[key] if f["elected"]]
    if len(elected) != 1:
        print(key, "elected", len(elected), "cands", len(by[key]))
        for f in by[key]:
            print(" ", f["elected"], f["candidate"], f["party"], f["value"], "row", f["source_cell"])
