# v1.0: 03-11/15/16 の raw_json・PDF・Excel 実体確認
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"


def main() -> None:
    for kaiji in range(44, 52):
        d = DATA / f"shugiin{kaiji}"
        raw = d / "raw"
        raw_json = d / "raw_json"
        print(f"\n## shugiin{kaiji} raw_json_dir={raw_json.exists()}")
        for p in sorted(raw.glob("03-1[156]*")):
            print(f"  RAW {p.name} size={p.stat().st_size}")
        if raw_json.exists():
            matches = sorted(raw_json.glob("03-1[156]*"))
            print(f"  raw_json matches={len(matches)}")
            for p in matches[:20]:
                print(f"  RJ {p.name} size={p.stat().st_size}")
        # also check if 03-11 in normalized coverage with 0?
        nman = d / "normalized" / "manifest.json"
        if nman.exists():
            nm = json.loads(nman.read_text(encoding="utf-8"))
            for c in nm.get("coverage") or []:
                if str(c.get("source_code", "")).startswith(("03-11", "03-15", "03-16")):
                    print(f"  COV {c}")


if __name__ == "__main__":
    main()
