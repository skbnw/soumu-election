#!/usr/bin/env python3
"""Deeper probe for 03-05 party blocks and 03-13 prefecture headers."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from soumu_election.normalize import matrix, compact

RAW = ROOT / "data" / "sangiin27" / "raw_json"


def load(prefix: str):
    path = next(RAW.glob(f"{prefix}_*.json"))
    doc = json.loads(path.read_text(encoding="utf-8"))
    return doc, matrix(doc, doc["sheets"][0])


def main():
    doc, table = load("03-05")
    print("=== 03-05 party header rows ===")
    for i, row in enumerate(table):
        parties = [compact(v) for v in row if compact(v) and ("党" in compact(v) or compact(v) in {"諸派", "無所属", "チームみらい", "再生の道", "無所属連合", "日本改革党", "日本誠真会", "ＮＨＫ党", "れいわ新選組", "参政党"})]
        label = compact(row[0] if row else None)
        if parties and len(parties) >= 2:
            print(f"R{i:03d} label={label!r} parties={parties}")
        if label == "都道府県" or (label and "政党等の名称" in label):
            print(f"R{i:03d} special={label!r} sample={[(c, compact(v)) for c,v in enumerate(row) if compact(v)][:12]}")

    print("\n=== 03-13 prefecture markers ===")
    _, t13 = load("03-13")
    pref_re = re.compile(r"^(.+?[都道府県])\(定数")
    for i, row in enumerate(t13):
        for c in (0, 7):
            text = compact(row[c] if c < len(row) else None)
            if text and pref_re.match(text):
                print(f"R{i:03d}C{c} {text}")
        for c in (0, 7):
            text = compact(row[c] if c < len(row) else None)
            if text in {"当", "落"}:
                name = compact(row[c+1] if c+1 < len(row) else None)
                votes = row[c+6] if c+6 < len(row) else None
                # only first 40 hits
                if i < 80:
                    print(f"  cand R{i}C{c} {text} {name} votes={votes}")

    print("\n=== unclassified sample headers ===")
    path = next(RAW.glob("unclassified_*.json"))
    doc = json.loads(path.read_text(encoding="utf-8"))
    table = matrix(doc, doc["sheets"][0])
    for i, row in enumerate(table[:40]):
        cells = [(c, compact(v)) for c, v in enumerate(row) if compact(v)]
        if cells:
            print(f"R{i:03d} {cells[:10]}")


if __name__ == "__main__":
    main()
