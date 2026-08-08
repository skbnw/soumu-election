# v1.0: 03-11/15/16 の原本形式一覧
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
TARGETS = {"03-11", "03-15", "03-16"}


def main() -> None:
    for kaiji in range(44, 52):
        m = json.loads((DATA / f"shugiin{kaiji}/manifest.json").read_text(encoding="utf-8"))
        print(f"\n## shugiin{kaiji}")
        for s in m.get("sources") or []:
            code = str(s.get("source_code") or "")
            base = code.split("-")
            key = "-".join(base[:2]) if len(base) >= 2 else code
            if key not in TARGETS and not code.startswith("03-15") and not code.startswith("03-16") and not code.startswith("03-11"):
                continue
            path = s.get("file") or ""
            title = s.get("title") or s.get("name") or ""
            full = DATA / f"shugiin{kaiji}" / path.replace("\\", "/")
            print(f"  {code} fmt={Path(path).suffix} exists={full.exists()} title={title}")
            print(f"    file={path}")
            raw_json = s.get("raw_json")
            if raw_json:
                rj = DATA / f"shugiin{kaiji}" / str(raw_json).replace("\\", "/")
                print(f"    raw_json_exists={rj.exists()} {raw_json}")


if __name__ == "__main__":
    main()
