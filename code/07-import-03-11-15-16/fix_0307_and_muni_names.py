# v1.0: 市町村名の空白除去 + 03-07 再取込 + warehouse 更新
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from soumu_election.download import workbook_to_raw_json, xls_to_raw_json
from soumu_election.normalize import matrix, parse_pr_prefecture_party
from soumu_election.warehouse import main as build_warehouse

DATA = ROOT / "data"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def source_meta(item: dict) -> dict:
    return {
        "dataset": item.get("dataset") or item.get("label") or "",
        "category": item.get("category") or "summary",
        "url": item.get("url") or "",
        "source_page": item.get("source_page") or "",
        "source_code": "03-07",
        "label": item.get("label") or "",
    }


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
    write_json(out_dir / "manifest.json", {
        "schema_version": "1.0",
        "records": len(facts),
        "normalized_sources": sum(c.get("status") == "normalized" for c in coverage),
        "domain_records": {k: len(v) for k, v in domains.items()},
        "coverage": coverage,
        "note": note,
    })


def reimport_0307(kaiji: int) -> int:
    election_dir = DATA / f"shugiin{kaiji}"
    manifest = load_json(election_dir / "manifest.json")
    items = [s for s in manifest.get("sources") or [] if str(s.get("source_code")) == "03-07"]
    if not items:
        print(f"  kaiji{kaiji}: no 03-07")
        return 0
    item = items[0]
    raw_path = election_dir / str(item.get("file") or "").replace("\\", "/")
    if not raw_path.exists():
        print(f"  kaiji{kaiji}: missing {raw_path}")
        return 0
    meta = source_meta(item)
    try:
        if raw_path.suffix.lower() == ".xls":
            try:
                doc = xls_to_raw_json(raw_path, meta, kaiji)
            except Exception:
                import xlrd
                book = xlrd.open_workbook(raw_path)
                sheets = []
                for ws in book.sheets():
                    cells = []
                    for r in range(ws.nrows):
                        for c in range(ws.ncols):
                            cell = ws.cell(r, c)
                            if cell.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
                                continue
                            value = cell.value
                            if cell.ctype == xlrd.XL_CELL_NUMBER and float(value).is_integer():
                                value = int(value)
                            cells.append({"cell": f"R{r+1}C{c+1}", "row": r + 1, "column": c + 1, "value": value})
                    sheets.append({"name": ws.name, "max_row": ws.nrows, "max_column": ws.ncols,
                                   "merged_cells": [], "cells": cells})
                doc = {
                    "schema_version": "1.0", "election_kaiji": kaiji, "dataset": meta["dataset"],
                    "category": meta["category"], "source_url": meta["url"],
                    "source_page": meta["source_page"], "source_file": raw_path.name, "sheets": sheets,
                }
        else:
            doc = workbook_to_raw_json(raw_path, meta, kaiji)
    except Exception as exc:
        print(f"  kaiji{kaiji}: raw fail {exc}")
        return 0
    doc["source_code"] = "03-07"
    doc["source_file"] = raw_path.name
    facts = []
    for sheet in doc["sheets"]:
        facts.extend(parse_pr_prefecture_party(doc, sheet, matrix(doc, sheet)))
    print(f"  kaiji{kaiji}: 03-07 facts={len(facts)}")

    norm_dir = election_dir / "normalized"
    old = load_json(norm_dir / "facts.json")
    kept = [f for f in old if f.get("source_code") != "03-07"]
    merged = kept + facts
    man = load_json(norm_dir / "manifest.json")
    coverage = [c for c in man.get("coverage") or [] if c.get("source_code") != "03-07"]
    coverage.append({
        "source_code": "03-07",
        "dataset": doc.get("dataset"),
        "status": "normalized" if facts else "raw_only",
        "records": len(facts),
    })
    coverage.sort(key=lambda c: str(c.get("source_code")))
    note = man.get("note") or ""
    if "03-07 header fix" not in note:
        note = f"{note}; 03-07 header fix".strip("; ")
    rebuild_domains(merged, norm_dir, coverage, note)
    return len(facts)


def fix_municipality_names() -> None:
    con = duckdb.connect()
    for rel in (
        DATA / "warehouse/parquet/municipality_facts.parquet",
        ROOT / "web/data/municipality_facts.parquet",
        DATA / "warehouse/parquet/smd_municipality_votes.parquet",
        ROOT / "web/data/smd_municipality_votes.parquet",
    ):
        if not rel.exists():
            continue
        tmp = rel.with_suffix(".tmp.parquet")
        con.execute(f"""
            COPY (
              SELECT * REPLACE (
                CASE WHEN municipality IS NULL THEN NULL
                     ELSE replace(replace(municipality, ' ', ''), chr(12288), '')
                END AS municipality
              )
              FROM read_parquet('{rel.as_posix()}')
            ) TO '{tmp.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)
        """)
        tmp.replace(rel)
        print(f"normalized names: {rel}")
    # count remaining spaces
    p = ROOT / "web/data/municipality_facts.parquet"
    print(con.sql(f"""
        SELECT count(*) AS still_spaced
        FROM read_parquet('{p.as_posix()}')
        WHERE municipality IS NOT NULL
          AND (municipality LIKE '% %' OR municipality LIKE '%　%')
    """))


def main() -> int:
    print("=== reimport 03-07 ===")
    for kaiji in range(44, 52):
        reimport_0307(kaiji)

    print("=== rebuild warehouse ===")
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
    shutil.copy2(src, dst)
    print(f"copied {src} -> {dst}")

    print("=== fix municipality names ===")
    fix_municipality_names()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
