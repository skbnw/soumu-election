# v1.1.0: 第45回以降の小選挙区候補者得票を整備し warehouse / web を更新
"""
既存 warehouse の facts から candidate_votes 以外を保持し、
03-13 を再パースした candidate_votes で置き換えて warehouse を再構築する。
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from soumu_election.normalize import matrix, parse_pdf_smd_candidates, parse_xls_smd_candidates
from soumu_election.warehouse import main as build_warehouse


def base_doc(path: Path, kaiji: int) -> dict:
    return {
        "schema_version": "1.0",
        "election_kaiji": kaiji,
        "dataset": "候補者別得票数（小選挙区）",
        "category": "当選人・得票",
        "source_code": "03-13",
        "source_url": "",
        "source_page": "",
        "source_file": path.name,
    }


def load_xls_doc(path: Path, kaiji: int) -> dict:
    import xlrd

    workbook = xlrd.open_workbook(str(path))
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
                    "cell": f"R{row + 1}C{column + 1}",
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
    doc = base_doc(path, kaiji)
    doc["sheets"] = sheets
    return doc


def parse_candidate_votes(kaiji: int) -> list[dict]:
    raw_dir = ROOT / "data" / f"shugiin{kaiji}" / "raw"
    path = sorted(raw_dir.glob("03-13*"))[0]
    if path.suffix.lower() == ".pdf":
        doc = base_doc(path, kaiji)
        doc["pages"] = []
        # Prefer config URL if available
        config = json.loads((ROOT / "config" / f"shugiin{kaiji}.json").read_text(encoding="utf-8"))
        for source in config.get("sources", []):
            if str(source.get("source_code") or "").startswith("03-13") or "候補者別得票" in str(source.get("dataset", "")):
                doc["source_url"] = source.get("url") or doc["source_url"]
                doc["dataset"] = source.get("dataset") or doc["dataset"]
                break
        return parse_pdf_smd_candidates(doc, path)
    if path.suffix.lower() == ".xls":
        doc = load_xls_doc(path, kaiji)
        config = json.loads((ROOT / "config" / f"shugiin{kaiji}.json").read_text(encoding="utf-8"))
        for source in config.get("sources", []):
            if "候補者別得票" in str(source.get("dataset", "")):
                doc["source_url"] = source.get("url") or doc["source_url"]
                doc["dataset"] = source.get("dataset") or doc["dataset"]
                break
        facts = []
        for sheet in doc["sheets"]:
            facts.extend(parse_xls_smd_candidates(doc, sheet, matrix(doc, sheet)))
        return facts
    raise ValueError(path)


def export_non_candidate_facts(kaiji: int) -> list[dict]:
    parquet = ROOT / "data" / "warehouse" / "parquet" / "facts.parquet"
    con = duckdb.connect()
    rows = con.execute(
        """
        SELECT contest, scope, prefecture, pr_block, party, justice, gender, age_band,
               candidate_status, row_variant, metric, value, unit, divisor, allocation_rank,
               source_code, dataset, source_url, source_file, source_sheet, source_cell,
               candidate, candidate_raw, district_number, elected, age, occupation,
               dual_candidacy, sekihairitsu, election_kaiji
        FROM read_parquet(?)
        WHERE election_kaiji = ?
          AND metric <> 'candidate_votes'
        """,
        [str(parquet), kaiji],
    ).fetchall()
    cols = [
        "contest", "scope", "prefecture", "pr_block", "party", "justice", "gender", "age_band",
        "candidate_status", "row_variant", "metric", "value", "unit", "divisor", "allocation_rank",
        "source_code", "dataset", "source_url", "source_file", "source_sheet", "source_cell",
        "candidate", "candidate_raw", "district_number", "elected", "age", "occupation",
        "dual_candidacy", "sekihairitsu", "election_kaiji",
    ]
    return [dict(zip(cols, row)) for row in rows]


def write_normalized(kaiji: int, facts: list[dict], candidate_count: int) -> None:
    out = ROOT / "data" / f"shugiin{kaiji}" / "normalized"
    out.mkdir(parents=True, exist_ok=True)
    (out / "facts.json").write_text(json.dumps(facts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Preserve previous coverage entries when possible; refresh 03-13.
    coverage = []
    old_manifest = out / "manifest.json"
    if old_manifest.exists():
        coverage = [
            entry for entry in json.loads(old_manifest.read_text(encoding="utf-8")).get("coverage", [])
            if entry.get("source_code") != "03-13"
        ]
    else:
        # Reconstruct rough coverage from source_code counts.
        counts: dict[str, int] = {}
        datasets: dict[str, str] = {}
        for item in facts:
            code = item.get("source_code") or ""
            counts[code] = counts.get(code, 0) + 1
            datasets[code] = item.get("dataset") or datasets.get(code)
        coverage = [
            {"source_code": code, "dataset": datasets.get(code), "status": "normalized", "records": count}
            for code, count in sorted(counts.items())
            if code != "03-13"
        ]
    coverage.append({
        "source_code": "03-13",
        "dataset": "候補者別得票数（小選挙区）",
        "status": "normalized" if candidate_count else "raw_only",
        "records": candidate_count,
    })
    candidate_metrics = {"candidates", "elected_candidates"}
    domains = {
        "candidate_facts.json": [item for item in facts if item.get("metric") in candidate_metrics],
        "candidate_vote_facts.json": [item for item in facts if item.get("metric") == "candidate_votes"],
        "party_facts.json": [item for item in facts if item.get("party") is not None],
        "turnout_facts.json": [
            item for item in facts
            if item.get("metric") not in candidate_metrics
            and item.get("party") is None
            and item.get("contest") != "judicial_review"
        ],
        "judicial_review_facts.json": [item for item in facts if item.get("contest") == "judicial_review"],
    }
    for filename, records in domains.items():
        (out / filename).write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": "1.0",
        "records": len(facts),
        "normalized_sources": sum(item["status"] == "normalized" for item in coverage),
        "domain_records": {filename: len(records) for filename, records in domains.items()},
        "coverage": coverage,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "note": "candidate_votes refreshed from 03-13 for kaiji 44-51",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    out_dir = Path(__file__).resolve().parent / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = []
    for kaiji in range(44, 52):
        print(f"parsing kaiji {kaiji} ...", flush=True)
        candidate_facts = parse_candidate_votes(kaiji)
        other = export_non_candidate_facts(kaiji)
        facts = other + candidate_facts
        write_normalized(kaiji, facts, len(candidate_facts))
        row = {
            "kaiji": kaiji,
            "candidate_votes": len(candidate_facts),
            "other_facts": len(other),
            "total_facts": len(facts),
        }
        summary.append(row)
        print(row, flush=True)

    (out_dir / "rebuild_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print("building warehouse ...", flush=True)
    old_argv = sys.argv
    try:
        sys.argv = [
            "warehouse",
            "--project-root", str(ROOT),
            "--output", str(ROOT / "data" / "warehouse"),
            "--kaiji", *[str(k) for k in range(44, 52)],
        ]
        rc = build_warehouse()
    finally:
        sys.argv = old_argv
    if rc != 0:
        print("warehouse validation reported failures; parquet was still written", flush=True)

    src = ROOT / "data" / "warehouse" / "parquet" / "facts.parquet"
    dest_dir = ROOT / "web" / "data"
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest_dir / "facts.parquet")
    print("copied to web/data/facts.parquet", flush=True)

    con = duckdb.connect()
    counts = con.execute(
        """
        SELECT election_kaiji, count(*) AS n
        FROM read_parquet(?)
        WHERE metric='candidate_votes'
        GROUP BY 1 ORDER BY 1
        """,
        [str(dest_dir / "facts.parquet")],
    ).fetchall()
    print("web candidate_votes", counts)
    (out_dir / "web_candidate_counts.json").write_text(
        json.dumps([{"kaiji": k, "n": n} for k, n in counts], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
