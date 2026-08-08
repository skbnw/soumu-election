# v1.0: 03-11 / 03-15 / 03-16 を原本から取り込み、normalized と warehouse を更新
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from soumu_election.download import pdf_to_raw_json, workbook_to_raw_json, xls_to_raw_json
from soumu_election.normalize import (
    matrix,
    parse_age_turnout_1819,
    parse_age_turnout_by_age,
    parse_pdf_age_turnout,
    parse_pdf_pr_elected,
    parse_xls_pr_elected,
)
from soumu_election.warehouse import main as build_warehouse

DATA = ROOT / "data"
TARGETS = {"03-11", "03-15", "03-16"}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def source_meta(item: dict, kaiji: int) -> dict:
    return {
        "dataset": item.get("dataset") or item.get("label") or item.get("title") or "",
        "category": item.get("category") or "summary",
        "url": item.get("url") or item.get("source_url") or "",
        "source_page": item.get("source_page") or item.get("page") or "",
        "source_code": item.get("source_code"),
        "label": item.get("label") or "",
    }


def base_code(code: str) -> str:
    code = str(code or "")
    if code.startswith("03-14"):
        return "03-14"
    parts = code.split("-")
    return "-".join(parts[:2]) if len(parts) >= 2 else code


def parse_doc(doc: dict, raw_path: Path) -> list[dict]:
    code = doc["source_code"]
    if "sheets" in doc:
        facts = []
        parser = {
            "03-11": parse_xls_pr_elected,
            "03-15": parse_age_turnout_1819,
            "03-16": parse_age_turnout_by_age,
        }.get(code)
        if not parser:
            return []
        for sheet in doc["sheets"]:
            facts.extend(parser(doc, sheet, matrix(doc, sheet)))
        return facts
    if code == "03-11":
        return parse_pdf_pr_elected(doc, raw_path)
    if code == "03-16":
        return parse_pdf_age_turnout(doc, raw_path)
    return []


def rebuild_domains(facts: list[dict], out_dir: Path, coverage: list[dict], note: str) -> None:
    candidate_metrics = {"candidates", "elected_candidates"}
    domains = {
        "candidate_facts.json": [item for item in facts if item["metric"] in candidate_metrics],
        "candidate_vote_facts.json": [item for item in facts if item["metric"] == "candidate_votes"],
        "party_facts.json": [item for item in facts if item.get("party") is not None],
        "turnout_facts.json": [
            item for item in facts
            if item["metric"] not in candidate_metrics
            and item.get("party") is None
            and item.get("contest") != "judicial_review"
        ],
        "judicial_review_facts.json": [item for item in facts if item.get("contest") == "judicial_review"],
    }
    write_json(out_dir / "facts.json", facts)
    for filename, records in domains.items():
        write_json(out_dir / filename, records)
    manifest = {
        "schema_version": "1.0",
        "records": len(facts),
        "normalized_sources": sum(item.get("status") == "normalized" for item in coverage),
        "domain_records": {filename: len(records) for filename, records in domains.items()},
        "coverage": coverage,
        "note": note,
    }
    write_json(out_dir / "manifest.json", manifest)


def process_kaiji(kaiji: int) -> dict:
    election_dir = DATA / f"shugiin{kaiji}"
    manifest = load_json(election_dir / "manifest.json")
    sources = [
        s for s in (manifest.get("sources") or [])
        if base_code(s.get("source_code")) in TARGETS
    ]
    # Prefer Excel over duplicate PDF for same code within an election
    by_code: dict[str, list[dict]] = {}
    for s in sources:
        by_code.setdefault(base_code(s.get("source_code")), []).append(s)
    selected = []
    for code, items in by_code.items():
        excel = [i for i in items if str(i.get("file") or "").lower().endswith((".xls", ".xlsx"))]
        pdf = [i for i in items if str(i.get("file") or "").lower().endswith(".pdf")]
        if code == "03-16" and excel:
            selected.extend(excel)
        elif code == "03-11" and excel:
            selected.extend(excel)
        else:
            selected.extend(excel or pdf)

    raw_json_dir = election_dir / "raw_json"
    raw_json_dir.mkdir(parents=True, exist_ok=True)

    new_facts: list[dict] = []
    coverage_updates: list[dict] = []
    for item in selected:
        rel = str(item.get("file") or "").replace("\\", "/")
        raw_path = election_dir / rel
        if not raw_path.exists():
            print(f"  MISSING {raw_path}")
            continue
        meta = source_meta(item, kaiji)
        suffix = raw_path.suffix.lower()
        if suffix == ".pdf":
            doc = pdf_to_raw_json(raw_path, meta, kaiji)
        elif suffix == ".xls":
            try:
                doc = xls_to_raw_json(raw_path, meta, kaiji)
            except Exception:
                import xlrd

                workbook = xlrd.open_workbook(raw_path)
                sheets = []
                for ws in workbook.sheets():
                    cells = []
                    for row in range(ws.nrows):
                        for column in range(ws.ncols):
                            cell = ws.cell(row, column)
                            if cell.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
                                continue
                            value = cell.value
                            if cell.ctype == xlrd.XL_CELL_NUMBER and float(value).is_integer():
                                value = int(value)
                            cells.append({
                                "cell": f"R{row+1}C{column+1}",
                                "row": row + 1,
                                "column": column + 1,
                                "value": value,
                            })
                    sheets.append({
                        "name": ws.name,
                        "max_row": ws.nrows,
                        "max_column": ws.ncols,
                        "merged_cells": [],
                        "cells": cells,
                    })
                doc = {
                    "schema_version": "1.0",
                    "election_kaiji": kaiji,
                    "dataset": meta["dataset"],
                    "category": meta["category"],
                    "source_url": meta["url"],
                    "source_page": meta["source_page"],
                    "source_file": raw_path.name,
                    "sheets": sheets,
                }
        else:
            doc = workbook_to_raw_json(raw_path, meta, kaiji)
        doc["source_code"] = base_code(item.get("source_code"))
        doc["source_file"] = raw_path.name
        doc["dataset"] = meta["dataset"] or doc.get("dataset")
        # keep raw_json for reproducibility of these codes
        write_json(raw_json_dir / f"{raw_path.stem}.json", doc)
        facts = parse_doc(doc, raw_path)
        print(f"  {doc['source_code']} {raw_path.name}: facts={len(facts)}")
        new_facts.extend(facts)
        coverage_updates.append({
            "source_code": doc["source_code"],
            "dataset": doc.get("dataset"),
            "status": "normalized" if facts else "raw_only",
            "records": len(facts),
        })

    norm_dir = election_dir / "normalized"
    facts_path = norm_dir / "facts.json"
    old_facts = load_json(facts_path) if facts_path.exists() else []
    kept = [f for f in old_facts if base_code(f.get("source_code")) not in TARGETS]
    merged = kept + new_facts

    man_path = norm_dir / "manifest.json"
    old_man = load_json(man_path) if man_path.exists() else {"coverage": []}
    coverage = [
        c for c in (old_man.get("coverage") or [])
        if base_code(c.get("source_code")) not in TARGETS
    ]
    # dedupe coverage_updates by source_code (keep last)
    seen = {}
    for c in coverage_updates:
        seen[c["source_code"]] = c
    coverage.extend(seen.values())
    coverage.sort(key=lambda c: str(c.get("source_code")))

    note = old_man.get("note") or ""
    extra = "imported 03-11/03-15/03-16"
    note = f"{note}; {extra}" if note and extra not in note else (note or extra)
    rebuild_domains(merged, norm_dir, coverage, note)
    return {
        "kaiji": kaiji,
        "added": len(new_facts),
        "total": len(merged),
        "coverage": list(seen.values()),
    }


def main() -> int:
    summaries = []
    for kaiji in range(44, 52):
        print(f"\n## shugiin{kaiji}")
        summaries.append(process_kaiji(kaiji))

    print("\n=== rebuild warehouse ===")
    argv = sys.argv[:]
    sys.argv = [
        "build_election_warehouse.py",
        "--project-root", str(ROOT),
        "--output", str(DATA / "warehouse"),
        "--kaiji", *[str(k) for k in range(44, 52)],
    ]
    try:
        rc = build_warehouse()
    finally:
        sys.argv = argv
    src = DATA / "warehouse/parquet/facts.parquet"
    dst = ROOT / "web/data/facts.parquet"
    if src.exists():
        shutil.copy2(src, dst)
        print(f"copied {src} -> {dst}")
    print(json.dumps(summaries, ensure_ascii=False, indent=2))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
