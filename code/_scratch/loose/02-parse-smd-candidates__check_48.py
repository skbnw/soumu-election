# v1.0: 第48回 Excel 03-13 の氏名パース確認
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from test_parse_03_13 import parse_kaiji

facts = parse_kaiji(48)
print("records", len(facts))
print("elected", sum(1 for f in facts if f.get("elected")))
print("sample", json.dumps([
    {
        "candidate": f["candidate"],
        "raw": f["candidate_raw"],
        "pref": f["prefecture"],
        "dist": f["district_number"],
        "votes": f["value"],
        "party": f["party"],
        "elected": f["elected"],
    }
    for f in facts[:8]
], ensure_ascii=False, indent=2))
