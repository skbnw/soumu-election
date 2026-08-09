# -*- coding: utf-8 -*-
"""
export_seiji_gakkai_pr_votes_v1.0.py
- 政治学会 SH-B Bronze → 比例政党得票の別 parquet（MIC facts に merge しない）
- source_code: seiji-gakkai-pr-{kaiji:02d}
- geo_level: block / national（都道府県粒は SH-B に無い）

出力:
  data/warehouse/parquet/seiji_gakkai_pr_votes.parquet
  web/data/seiji_gakkai_pr_votes.parquet
"""
from __future__ import annotations

import json
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parents[2]
SHB = (
    REPO
    / "references"
    / "seiji-gakkai"
    / "01-bronze"
    / "1996-2017"
    / "04-SH-B"
    / "shb-blocks.jsonl"
)
WAREHOUSE_OUT = REPO / "data" / "warehouse" / "parquet" / "seiji_gakkai_pr_votes.parquet"
WEB_OUT = REPO / "web" / "data" / "seiji_gakkai_pr_votes.parquet"
OUT_DIR = REPO / "output" / "04-seiji-gakkai"

BLOCK_NORM = {
    "北海道": "北海道",
    "東北": "東北",
    "北関東": "北関東",
    "南関東": "南関東",
    "東京": "東京都",
    "東京都": "東京都",
    "北陸信越": "北陸信越",
    "東海": "東海",
    "近畿": "近畿",
    "中国": "中国",
    "四国": "四国",
    "九州": "九州",
}


def nfkc(value: str | None) -> str:
    return unicodedata.normalize("NFKC", str(value or "").strip())


def main() -> None:
    if not SHB.is_file():
        raise SystemExit(f"missing SH-B: {SHB}")

    rows: list[dict] = []
    national: dict[tuple[int, int, str], dict] = defaultdict(
        lambda: {"votes": 0, "seats": 0, "n_candidates": 0}
    )

    with SHB.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            th = int(rec["election_th"])
            year = int(rec["election_year"])
            block = BLOCK_NORM.get(nfkc(rec.get("block_name")), nfkc(rec.get("block_name")))
            source_code = f"seiji-gakkai-pr-{th:02d}"
            eligible = rec.get("eligible_voters")
            for party in rec.get("parties") or []:
                name = nfkc(party.get("party_name"))
                if not name or name in ("合計", "計"):
                    continue
                votes = party.get("votes")
                seats = party.get("seats")
                n_cand = party.get("n_candidates")
                rows.append(
                    {
                        "election_kaiji": th,
                        "election_year": year,
                        "election_id": f"shugiin-{th}",
                        "contest": "pr",
                        "geo_level": "block",
                        "pr_block": block,
                        "prefecture": None,
                        "party": name,
                        "metric": "party_votes",
                        "value": int(votes) if votes is not None else None,
                        "unit": "votes",
                        "party_seats": int(seats) if seats is not None else None,
                        "n_candidates": int(n_cand) if n_cand is not None else None,
                        "block_eligible_voters": int(eligible) if eligible is not None else None,
                        "source_code": source_code,
                        "dataset": "政治学会・比例ブロック（SH-B）",
                        "source_file": rec.get("source_file"),
                        "source": "seiji-gakkai",
                    }
                )
                if votes is not None:
                    key = (th, year, name)
                    national[key]["votes"] += int(votes)
                    if seats is not None:
                        national[key]["seats"] += int(seats)
                    if n_cand is not None:
                        national[key]["n_candidates"] += int(n_cand)

    for (th, year, party), agg in sorted(national.items()):
        rows.append(
            {
                "election_kaiji": th,
                "election_year": year,
                "election_id": f"shugiin-{th}",
                "contest": "pr",
                "geo_level": "national",
                "pr_block": "全国",
                "prefecture": None,
                "party": party,
                "metric": "party_votes",
                "value": agg["votes"],
                "unit": "votes",
                "party_seats": agg["seats"],
                "n_candidates": agg["n_candidates"],
                "block_eligible_voters": None,
                "source_code": f"seiji-gakkai-pr-{th:02d}",
                "dataset": "政治学会・比例ブロック（SH-B）",
                "source_file": None,
                "source": "seiji-gakkai",
            }
        )

    if not rows:
        raise SystemExit("no PR rows")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    staging = OUT_DIR / f"{stamp}_seiji_gakkai_pr_votes.jsonl"
    with staging.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    WAREHOUSE_OUT.parent.mkdir(parents=True, exist_ok=True)
    WEB_OUT.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(
        f"""
        COPY (
          SELECT * FROM read_json_auto('{staging.as_posix()}')
          ORDER BY election_kaiji, geo_level, pr_block NULLS LAST, value DESC NULLS LAST, party
        ) TO '{WAREHOUSE_OUT.as_posix()}' (FORMAT PARQUET)
        """
    )
    WEB_OUT.write_bytes(WAREHOUSE_OUT.read_bytes())

    by = Counter((r["geo_level"], r["election_kaiji"]) for r in rows)
    report = [
        "# 政治学会 SH-B → seiji_gakkai_pr_votes エクスポート",
        f"generated_at={datetime.now().isoformat(timespec='seconds')}",
        f"rows={len(rows)}",
        f"warehouse_out={WAREHOUSE_OUT}",
        f"web_out={WEB_OUT}",
        "",
        "## counts by geo_level/kaiji",
    ]
    for key, n in sorted(by.items()):
        report.append(f"- {key}: {n}")
    report.append("")
    report.append("- MIC facts へは merge しない")
    report.append("- 都道府県粒なし（SH-B はブロック集計）")
    report_path = OUT_DIR / f"{stamp}_pr_export_report.txt"
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    (OUT_DIR / "pr_export_report.txt").write_text(report_path.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"wrote {len(rows)} rows -> {WEB_OUT}")
    print(f"report -> {report_path}")


if __name__ == "__main__":
    main()
