# -*- coding: utf-8 -*-
"""
export_yomi_pr_meibo.py v1.2
- v1.2: 衆41〜（1996〜）を含む。記事 Bronze に 41〜43 があるため下限を撤廃
- v1.1: 入力を本リポ output/02-yomi-prlist/pr_block_meibo.jsonl に変更
        （references 記事 → build_yomi_pr_meibo_from_articles_v1.0.py の成果）
- v1.0: polidata silver JSONL を直接変換

対象: 第41回以降（読売紙面記事）
出力: web/data/yomi_pr_meibo.parquet
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parents[2]
YOMI_JSONL = REPO / "output" / "02-yomi-prlist" / "pr_block_meibo.jsonl"
# フォールバック: 未ビルド時は polidata silver
YOMI_JSONL_FALLBACK = (
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

DISTRICT_IN_NAME_RE = __import__("re").compile(r"〈([^〉]+)〉")


def display_name_and_dual(raw_name: str, dual_district: str | None) -> tuple[str, str | None]:
    name = (raw_name or "").strip()
    dual = (dual_district or "").strip() or None
    if dual in ("", "単独"):
        dual = None if dual == "" else "単独"
    # 氏名に〈北海道４〉が付いている場合は重複立候補欄へ移す
    m = DISTRICT_IN_NAME_RE.search(name)
    if m:
        tag = m.group(1).strip()
        if tag and tag != "単独" and dual in (None, "単独"):
            dual = tag
        name = DISTRICT_IN_NAME_RE.sub("", name).strip()
    return name, dual


def main() -> None:
    src = YOMI_JSONL if YOMI_JSONL.is_file() else YOMI_JSONL_FALLBACK
    if not src.is_file():
        raise SystemExit(
            f"missing yomi meibo jsonl.\n"
            f"  run: python code/02-yomi-prlist/build_yomi_pr_meibo_from_articles_v1.0.py\n"
            f"  looked: {YOMI_JSONL} / {YOMI_JSONL_FALLBACK}"
        )

    rows = []
    with src.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            o = json.loads(line)
            th = o.get("th")
            if not th or int(th) < 41:
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
            cand, dual = display_name_and_dual(
                o.get("candidate_name") or "",
                o.get("dual_district"),
            )
            rows.append(
                {
                    "election_kaiji": int(th),
                    "year": int(o["year"]) if o.get("year") else None,
                    "pr_block": block,
                    "party_short": party,
                    "party": PARTY_LABEL.get(party, party),
                    "list_rank": o.get("meibo_rank"),
                    "candidate": cand,
                    "party_seats": o.get("party_seats_won"),
                    "sekihai_rate": o.get("sekihairitsu"),
                    "dual_district": dual,
                    "result_status": status or None,
                    "outcome": outcome,
                    "source": o.get("name_source") or "yomi_print_article",
                }
            )

    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    staging = OUTPUT_DIR / f"{stamp}_yomi_pr_meibo_web.jsonl"
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
    print(f"source={src}")
    print(f"wrote {n} rows -> {WEB_OUT}")
    print(f"staging -> {staging}")


if __name__ == "__main__":
    main()
