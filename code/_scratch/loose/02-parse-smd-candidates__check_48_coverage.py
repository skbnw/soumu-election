# v1.0: 第48回で欠落候補・当選者数を点検
import sys
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from test_parse_03_13 import parse_kaiji

facts = parse_kaiji(48)
names = [f["candidate"] for f in facts]
print("has 池田真紀", "池田真紀" in names)
print("has 和田義明", "和田義明" in names)
by_dist = Counter((f["prefecture"], f["district_number"]) for f in facts)
print("districts", len(by_dist))
print("elected", sum(1 for f in facts if f["elected"]))
# districts with !=1 elected
bad = [(k, sum(1 for f in facts if (f["prefecture"], f["district_number"]) == k and f["elected"]))
       for k in by_dist]
multi = [x for x in bad if x[1] != 1]
print("districts not exactly 1 elected", len(multi))
print("examples", multi[:10])
# Hokkaido districts present
hokkaido = sorted(d for p, d in by_dist if p == "北海道")
print("hokkaido districts", hokkaido)
