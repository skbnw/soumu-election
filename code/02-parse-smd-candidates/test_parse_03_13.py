# v1.0: 03-13 候補者得票パーサを各回で試行し件数を確認
"""Parse 03-13 for kaiji 44-51 without writing warehouse."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from soumu_election.normalize import matrix, parse_pdf_smd_candidates, parse_xls_smd_candidates


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


def parse_kaiji(kaiji: int) -> list[dict]:
    raw_dir = ROOT / "data" / f"shugiin{kaiji}" / "raw"
    files = sorted(raw_dir.glob("03-13*"))
    if not files:
        raise FileNotFoundError(f"no 03-13 for {kaiji}")
    path = files[0]
    if path.suffix.lower() == ".pdf":
        doc = base_doc(path, kaiji)
        doc["pages"] = []
        return parse_pdf_smd_candidates(doc, path)
    if path.suffix.lower() == ".xls":
        doc = load_xls_doc(path, kaiji)
        facts = []
        for sheet in doc["sheets"]:
            facts.extend(parse_xls_smd_candidates(doc, sheet, matrix(doc, sheet)))
        return facts
    raise ValueError(f"unsupported {path}")


def main() -> None:
    out_dir = Path(__file__).resolve().parent / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = []
    for kaiji in range(44, 52):
        facts = parse_kaiji(kaiji)
        prefs = sorted({f.get("prefecture") for f in facts if f.get("prefecture")})
        districts = {(f.get("prefecture"), f.get("district_number")) for f in facts}
        elected = sum(1 for f in facts if f.get("elected"))
        row = {
            "kaiji": kaiji,
            "records": len(facts),
            "prefectures": len(prefs),
            "districts": len(districts),
            "elected": elected,
            "sample": {
                "candidate": facts[0].get("candidate"),
                "prefecture": facts[0].get("prefecture"),
                "district_number": facts[0].get("district_number"),
                "value": facts[0].get("value"),
                "party": facts[0].get("party"),
            } if facts else None,
        }
        summary.append(row)
        print(json.dumps({k: row[k] for k in ("kaiji", "records", "prefectures", "districts", "elected", "sample")}, ensure_ascii=False))
    (out_dir / "parser_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
