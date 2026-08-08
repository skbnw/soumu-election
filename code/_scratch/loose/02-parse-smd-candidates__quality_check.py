# v1.0: 各回の当選者数・選挙区数と公式定数の比較
import json
import sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from test_parse_03_13 import parse_kaiji

# SMD seat counts by kaiji
EXPECTED = {44: 300, 45: 300, 46: 300, 47: 295, 48: 289, 49: 289, 50: 289, 51: 289}
summary = []
for kaiji in range(44, 52):
    facts = parse_kaiji(kaiji)
    by = defaultdict(list)
    for f in facts:
        by[(f["prefecture"], f["district_number"])].append(f)
    elected = sum(1 for f in facts if f.get("elected"))
    bad = sum(1 for key, rows in by.items() if sum(1 for r in rows if r.get("elected")) != 1)
    summary.append({
        "kaiji": kaiji,
        "records": len(facts),
        "districts": len(by),
        "elected": elected,
        "expected_seats": EXPECTED[kaiji],
        "districts_bad_elected": bad,
    })
    print(summary[-1])

out = Path(__file__).resolve().parent / "output"
out.mkdir(exist_ok=True)
(out / "quality_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
