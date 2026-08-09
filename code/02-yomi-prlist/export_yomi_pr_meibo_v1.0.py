# -*- coding: utf-8 -*-
"""
export_yomi_pr_meibo.py v1.0
- 読売紙面の衆院比例ブロック名簿（pr_block_meibo.jsonl）を web 用 parquet に変換
- 対象: 第44回以降（MIC 03-11 と重なる範囲）
- 追加: party_label（表示用のやや長い党名）、pr_block の東京都正規化
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parents[2]
YOMI_JSONL = (
    Path(r"C:\Users\SKBNW\Documents\Github\polidata_national_elections")
    / "01-sources"
    / "yomi"
    / "02-silver"
    / "01_shugiin"
    / "pr_block_meibo"
    / "pr_block_meibo.jsonl"
)
WEB_OUT = REPO / "web" / "data" / "yomi_pr_meibo.parquet"
OUTPUT_DIR = REPO / "output" / "02-yomi-prlist"

# 記事略称 → UI表示用（総務省フルネームに寄せる）
PARTY_LABEL = {
    "自民": "自由民主党",
    "民主": "民主党",
    "民主党": "民主党",
    "共産": "日本共産党",
    "公明": "公明党",
    "維新": "日本維新の会",
    "国民": "国民民主党",
    "立民": "立憲民主党",
    "立憲民主": "立憲民主党",
    "立憲民": "立憲民主党",
    "社民": "社会民主党",
    "れいわ": "れいわ新選組",
    "参政": "参政党",
    "希望": "希望の党",
    "幸福": "幸福実現党",
    "みんな": "みんなの党",
    "新進": "新進党",
    "次世代": "次世代の党",
    "生活": "生活の党",
    "保守": "日本保守党",
    "日本保守": "日本保守党",
    "中道": "中道改革連合",
    "みらい": "チームみらい",
    "減ゆう": "減税日本・ゆうこく連合",
    "大地": "新党大地",
    "未来": "日本未来の党",
    "さきがけ": "新党さきがけ",
    "新社会": "新社会党",
    "こころ": "日本のこころ",
    "民進": "民進党",
    "自由": "自由党",
    "改革": "改革クラブ",
    "日本": "日本党",
}

BLOCK_NORM = {
    "東京": "東京都",
    "東京都": "東京都",
}


def main() -> None:
    if not YOMI_JSONL.is_file():
        raise SystemExit(f"missing yomi meibo: {YOMI_JSONL}")

    rows = []
    with YOMI_JSONL.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            o = json.loads(line)
            th = o.get("th")
            if not th or int(th) < 44:
                continue
            party = (o.get("party") or o.get("party_key") or "").strip()
            block = BLOCK_NORM.get(o.get("pr_block_name") or "", o.get("pr_block_name") or "")
            status = (o.get("result_status") or "").strip()
            if o.get("is_elected_smd"):
                outcome = "smd"
            elif o.get("is_elected_pr") or status in ("当", "比当"):
                outcome = "pr"
            else:
                outcome = "loss"
            rows.append(
                {
                    "election_kaiji": int(th),
                    "year": int(o["year"]) if o.get("year") else None,
                    "pr_block": block,
                    "party_short": party,
                    "party": PARTY_LABEL.get(party, party),
                    "list_rank": o.get("meibo_rank"),
                    "candidate": (o.get("candidate_name") or "").strip(),
                    "party_seats": o.get("party_seats_won"),
                    "sekihai_rate": o.get("sekihairitsu"),
                    "dual_district": (o.get("dual_district") or "").strip() or None,
                    "result_status": status or None,
                    "outcome": outcome,
                    "source": "yomi_print_article",
                }
            )

    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    staging = OUTPUT_DIR / f"{stamp}_yomi_pr_meibo.jsonl"
    with staging.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    WEB_OUT.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(
        f"""
        COPY (
          SELECT * FROM read_json_auto('{staging.as_posix()}')
          ORDER BY election_kaiji, pr_block, party, list_rank, candidate
        ) TO '{WEB_OUT.as_posix()}' (FORMAT PARQUET)
        """
    )
    n = con.execute(f"SELECT count(*) FROM read_parquet('{WEB_OUT.as_posix()}')").fetchone()[0]
    print(f"wrote {n} rows -> {WEB_OUT}")
    print(f"staging -> {staging}")


if __name__ == "__main__":
    main()
