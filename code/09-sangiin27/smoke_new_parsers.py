#!/usr/bin/env python3
"""Smoke-test new sangiin parsers on raw_json samples."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from soumu_election.normalize import matrix
from soumu_election.normalize_sangiin import SANGIIN_PARSERS

RAW = ROOT / "data" / "sangiin27" / "raw_json"


def run(code: str) -> list[dict]:
    path = next(RAW.glob(f"{code}_*.json"))
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["source_code"] = code
    parser = SANGIIN_PARSERS[code]
    facts = []
    for sheet in doc["sheets"]:
        facts.extend(parser(doc, sheet, matrix(doc, sheet)))
    return facts


def main() -> int:
    for code in ("03-05", "03-09", "03-10", "03-13"):
        facts = run(code)
        metrics = Counter(f["metric"] for f in facts)
        prefs = Counter(f.get("prefecture") for f in facts if f.get("prefecture"))
        print(f"{code}: {len(facts)} facts metrics={dict(metrics)}")
        if code == "03-13":
            print(f"  prefs={len(prefs)} elected={sum(1 for f in facts if f.get('elected'))}")
            seats = Counter(f.get("district_number") for f in facts)
            print(f"  seats={dict(sorted((k,v) for k,v in seats.items() if k is not None))}")
            print(f"  sample={[(f['prefecture'], f.get('district_number'), f['candidate'], f['value']) for f in facts[:5]]}")
            missing = {"鳥取県・島根県", "徳島県・高知県"} - set(prefs)
            print(f"  combined missing={missing}")
        if code == "03-05":
            parties = sorted({f["party"] for f in facts if f["metric"] == "party_votes"})
            print(f"  parties({len(parties)})={parties}")
            print(f"  party_votes rows={metrics.get('party_votes')}")
        if code == "03-10":
            print(f"  parties={sorted({f['party'] for f in facts})}")
            print(f"  elected={sum(1 for f in facts if f.get('elected'))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
