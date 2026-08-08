#!/usr/bin/env python3
# Rename misclassified 合同選挙区 files pr -> district and patch manifest
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "sangiin26" / "raw"
RAW_JSON = ROOT / "data" / "sangiin26" / "raw_json"
MANIFEST = ROOT / "data" / "sangiin26" / "manifest.json"


def main() -> int:
    mis = sorted(RAW.glob("03-14-pr-*_合同選挙区_*.xlsx"))
    if not mis:
        print("nothing to rename")
        return 0
    # next district index
    existing = list(RAW.glob("03-14-district-*.xlsx"))
    start = len(existing) + 1
    mapping: dict[str, str] = {}
    for offset, path in enumerate(mis):
        new_code = f"03-14-district-{start + offset:02d}"
        rest = path.name.split("_", 1)[1]  # drop old code
        new_name = f"{new_code}_{rest}"
        new_path = path.with_name(new_name)
        print(f"{path.name} -> {new_name}")
        path.rename(new_path)
        mapping[path.name] = new_name
        # raw_json
        old_json = RAW_JSON / f"{path.stem}.json"
        if old_json.exists():
            data = json.loads(old_json.read_text(encoding="utf-8"))
            data["category"] = "district"
            data["source_code"] = new_code
            data["source_file"] = new_name
            new_json = RAW_JSON / f"{new_path.stem}.json"
            new_json.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            old_json.unlink()

    if MANIFEST.exists() and mapping:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        for item in manifest.get("sources", []):
            file_name = Path(str(item.get("file", "")).replace("\\", "/")).name
            if file_name in mapping:
                new_name = mapping[file_name]
                item["file"] = f"raw/{new_name}"
                item["category"] = "district"
                item["source_code"] = new_name.split("_", 1)[0]
                stem = Path(new_name).stem
                item["raw_json"] = f"raw_json/{stem}.json"
        MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print("manifest patched", len(mapping))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
