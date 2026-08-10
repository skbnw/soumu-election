# -*- coding: utf-8 -*-
"""
参院 MIC 03-13 県名の取り違えを読売選挙DBで補正
v1.0
- 対象: facts の sangiin / contest=district / metric=candidate_votes / source_code=03-13
- 同一回・候補者名が senkyoDB 県区で一意のときだけ prefecture / prefecture_code を更新
- 得票・当落などの数値は変更しない（表示・県フィルタの正しさ用）
- 原本 raw_json / MIC ファイルは改変しない

背景:
  03-13 の左右パネルで県ヘッダと候補行がずれ、隣県に載ることがある（参27で確認）。
  パーサの他パネルへの県コピーは停止済みだが、ヘッダ欠落レイアウトは残る。

出力:
  web/data/facts.parquet と warehouse を更新
  output/06-yomi-senkyodb-list/*_patch_sangiin_district_pref_report.txt
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parents[2]
FACTS_WEB = REPO / "web" / "data" / "facts.parquet"
FACTS_WARE = REPO / "data" / "warehouse" / "parquet" / "facts.parquet"
SENKYODB = REPO / "web" / "data" / "yomi_senkyodb_candidates.parquet"
OUT_DIR = REPO / "output" / "06-yomi-senkyodb-list"

PREFECTURE_CODES = {
    name: f"{index:02d}" for index, name in enumerate((
        "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
        "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
        "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県", "岐阜県",
        "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県",
        "奈良県", "和歌山県", "鳥取県", "島根県", "岡山県", "広島県", "山口県",
        "徳島県", "香川県", "愛媛県", "高知県", "福岡県", "佐賀県", "長崎県",
        "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県",
    ), 1)
}
# 合区は MIC 表記。コードは代表側
PREFECTURE_CODES["鳥取県・島根県"] = "31"
PREFECTURE_CODES["徳島県・高知県"] = "36"

TARGET_KAIJI = (25, 27)


def main() -> None:
    if not FACTS_WEB.is_file() or not SENKYODB.is_file():
        raise SystemExit("facts or senkyodb parquet missing")

    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()

    db_rows = con.execute(
        f"""
        SELECT election_kaiji, candidate_name, prefecture, count(*) AS n
        FROM read_parquet('{SENKYODB.as_posix().replace("'", "''")}')
        WHERE chamber = 'sangiin'
          AND contest = 'district'
          AND election_kaiji IN ({",".join(str(k) for k in TARGET_KAIJI)})
          AND candidate_name IS NOT NULL
          AND prefecture IS NOT NULL
        GROUP BY 1,2,3
        """
    ).fetchall()

    # kaiji -> name -> set(prefs)
    by_kaiji: dict[int, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for kaiji, name, pref, _n in db_rows:
        by_kaiji[int(kaiji)][str(name)].add(str(pref))

    unique_map: dict[tuple[int, str], str] = {}
    for kaiji, names in by_kaiji.items():
        for name, prefs in names.items():
            if len(prefs) == 1:
                unique_map[(kaiji, name)] = next(iter(prefs))

    facts = con.execute(
        f"""
        SELECT election_kaiji, prefecture, prefecture_code, candidate, value
        FROM read_parquet('{FACTS_WEB.as_posix().replace("'", "''")}')
        WHERE election_id LIKE 'sangiin-%'
          AND contest = 'district'
          AND metric = 'candidate_votes'
          AND source_code = '03-13'
          AND election_kaiji IN ({",".join(str(k) for k in TARGET_KAIJI)})
        """
    ).fetchall()

    # 同一回・同一氏名が facts 内で一意の行だけパッチ（得票の float 差を避ける）
    fact_name_counts: dict[tuple[int, str], int] = Counter()
    for kaiji, pref, code, cand, vote in facts:
        fact_name_counts[(int(kaiji), str(cand))] += 1

    patches: list[dict] = []
    skipped_ambiguous = 0
    skipped_missing = 0
    skipped_dup_fact = 0
    already_ok = 0
    for kaiji, pref, code, cand, vote in facts:
        key = (int(kaiji), str(cand))
        if fact_name_counts[key] != 1:
            skipped_dup_fact += 1
            continue
        db_pref = unique_map.get(key)
        if db_pref is None:
            prefs = by_kaiji.get(int(kaiji), {}).get(str(cand))
            if prefs and len(prefs) > 1:
                skipped_ambiguous += 1
            else:
                skipped_missing += 1
            continue
        if db_pref == pref:
            already_ok += 1
            continue
        new_code = PREFECTURE_CODES.get(db_pref)
        patches.append(
            {
                "election_kaiji": int(kaiji),
                "candidate": str(cand),
                "old_prefecture": pref,
                "old_prefecture_code": code,
                "new_prefecture": db_pref,
                "new_prefecture_code": new_code,
            }
        )

    if not patches:
        print("no patches needed")
        con.close()
        return

    # apply via temp map join
    patch_path = OUT_DIR / f"{stamp}_district_pref_patches.jsonl"
    with patch_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in patches:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    src = FACTS_WEB.as_posix().replace("'", "''")
    patch_sql = patch_path.as_posix().replace("'", "''")
    tmp_out = OUT_DIR / f"{stamp}_facts_patched.parquet"
    dst = tmp_out.as_posix().replace("'", "''")

    con.execute(
        f"""
        COPY (
          WITH p AS (
            SELECT election_kaiji::BIGINT AS election_kaiji,
                   candidate,
                   new_prefecture,
                   new_prefecture_code
            FROM read_json_auto('{patch_sql}', format='newline_delimited', union_by_name=true)
          )
          SELECT
            f.* EXCLUDE (prefecture, prefecture_code),
            coalesce(p.new_prefecture, f.prefecture) AS prefecture,
            coalesce(p.new_prefecture_code, f.prefecture_code) AS prefecture_code
          FROM read_parquet('{src}') f
          LEFT JOIN p
            ON f.election_id LIKE 'sangiin-%'
           AND f.contest = 'district'
           AND f.metric = 'candidate_votes'
           AND f.source_code = '03-13'
           AND f.election_kaiji = p.election_kaiji
           AND f.candidate = p.candidate
        ) TO '{dst}' (FORMAT PARQUET, COMPRESSION ZSTD)
        """
    )

    data = tmp_out.read_bytes()
    FACTS_WEB.write_bytes(data)
    FACTS_WARE.parent.mkdir(parents=True, exist_ok=True)
    FACTS_WARE.write_bytes(data)

    # 定数(district_number)は raw 03-13 の県ヘッダ「定数N名」で揃える
    seat_rows: list[tuple[int, str, int]] = []
    pref_re = re.compile(r"^(.+?)\(定数(\d+)(?:\((\d+)\))?名\)")
    for kaiji in TARGET_KAIJI:
        raw_dir = REPO / "data" / f"sangiin{kaiji}" / "raw_json"
        path = next(raw_dir.glob("03-13_*.json"), None) if raw_dir.is_dir() else None
        if not path:
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        # local import to avoid hard dep if normalize unavailable
        sys_path_added = False
        if str(REPO / "src") not in sys.path:
            sys.path.insert(0, str(REPO / "src"))
            sys_path_added = True
        from soumu_election.normalize import compact, matrix  # noqa: WPS433
        for sheet in doc["sheets"]:
            table = matrix(doc, sheet)
            for row in table:
                for cell in row:
                    text = compact(cell)
                    matched = pref_re.match(text) if text else None
                    if not matched:
                        continue
                    pref = matched.group(1)
                    if not any(x in pref for x in ("都", "道", "府", "県")):
                        continue
                    seat_rows.append((kaiji, pref, int(matched.group(2))))
        if sys_path_added:
            pass

    if seat_rows:
        # dedupe last-wins
        seat_map = {(k, p): n for k, p, n in seat_rows}
        values = ",".join(f"({k}, '{p}', {n})" for (k, p), n in seat_map.items())
        seats_tmp = OUT_DIR / f"{stamp}_facts_seats.parquet"
        seats_dst = seats_tmp.as_posix().replace("'", "''")
        web_src = FACTS_WEB.as_posix().replace("'", "''")
        con.execute(
            f"""
            COPY (
              WITH seat AS (
                SELECT * FROM (VALUES {values}) t(election_kaiji, prefecture, seats)
              ),
              base AS (SELECT * FROM read_parquet('{web_src}'))
              SELECT
                b.* EXCLUDE (district_number),
                CASE
                  WHEN b.election_id LIKE 'sangiin-%'
                   AND b.contest='district'
                   AND b.metric='candidate_votes'
                   AND b.source_code='03-13'
                   AND s.seats IS NOT NULL
                  THEN s.seats
                  ELSE b.district_number
                END AS district_number
              FROM base b
              LEFT JOIN seat s
                ON b.election_kaiji = s.election_kaiji
               AND b.prefecture = s.prefecture
            ) TO '{seats_dst}' (FORMAT PARQUET, COMPRESSION ZSTD)
            """
        )
        data2 = seats_tmp.read_bytes()
        FACTS_WEB.write_bytes(data2)
        FACTS_WARE.write_bytes(data2)
        seats_tmp.unlink(missing_ok=True)

    # verify Nishida
    check = con.execute(
        f"""
        SELECT prefecture, candidate, value
        FROM read_parquet('{FACTS_WEB.as_posix().replace("'", "''")}')
        WHERE election_id LIKE 'sangiin-27%'
          AND contest='district' AND metric='candidate_votes'
          AND candidate IN ('西田昌司','倉林明子','滝沢求','福士珠美','岡崎太')
        ORDER BY candidate
        """
    ).fetchall()

    remaining = con.execute(
        f"""
        WITH f AS (
          SELECT election_kaiji, prefecture AS fact_pref, candidate
          FROM read_parquet('{FACTS_WEB.as_posix().replace("'", "''")}')
          WHERE election_id LIKE 'sangiin-%'
            AND contest='district' AND metric='candidate_votes'
            AND source_code='03-13'
            AND election_kaiji IN (25,27)
        ),
        d AS (
          SELECT election_kaiji, prefecture AS db_pref, candidate_name
          FROM read_parquet('{SENKYODB.as_posix().replace("'", "''")}')
          WHERE chamber='sangiin' AND contest='district'
            AND election_kaiji IN (25,27)
        )
        SELECT f.election_kaiji, count(*) FILTER (WHERE d.db_pref IS NOT NULL AND d.db_pref <> f.fact_pref)
        FROM f
        LEFT JOIN d ON d.election_kaiji=f.election_kaiji AND d.candidate_name=f.candidate
        GROUP BY 1 ORDER BY 1
        """
    ).fetchall()

    by_move = Counter((p["old_prefecture"], p["new_prefecture"]) for p in patches)
    report = OUT_DIR / f"{stamp}_patch_sangiin_district_pref_report.txt"
    lines = [
        f"patch sangiin 03-13 district pref ({stamp})",
        f"patches={len(patches)} already_ok={already_ok} "
        f"skipped_missing={skipped_missing} skipped_ambiguous={skipped_ambiguous} "
        f"skipped_dup_fact={skipped_dup_fact}",
        f"facts_web={FACTS_WEB}",
        "",
        "sample moves:",
    ]
    for (a, b), n in by_move.most_common(20):
        lines.append(f"  {a} -> {b}: {n}")
    lines.append("")
    lines.append("verify names:")
    for row in check:
        lines.append(f"  {row}")
    lines.append("")
    lines.append("remaining mismatches vs senkyodb:")
    for row in remaining:
        lines.append(f"  {row}")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(report.read_text(encoding="utf-8"))
    tmp_out.unlink(missing_ok=True)
    con.close()


if __name__ == "__main__":
    main()
