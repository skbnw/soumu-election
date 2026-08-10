# -*- coding: utf-8 -*-
"""
verify_sh_d_silver_v1.0.py
- 政治学会 SH-D Silver の検証レポート
- 選挙区数・票合計整合・政党補完・MIC(44-48)との選挙区数対比
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parents[2]
SILVER = (
    REPO
    / "references"
    / "seiji-gakkai"
    / "02-silver"
    / "1996-2017"
    / "03-SH-D"
    / "sh-d-votes.jsonl"
)
BRONZE = (
    REPO
    / "references"
    / "seiji-gakkai"
    / "01-bronze"
    / "1996-2017"
    / "03-SH-D"
    / "sh-d-votes.jsonl"
)
FACTS = REPO / "web" / "data" / "facts.parquet"
OUT_DIR = REPO / "output" / "04-seiji-gakkai"

# DS / 区割り想定（REPORT と整合）
EXPECTED_DISTRICTS = {
    41: 300,
    42: 300,
    43: 300,
    44: 300,
    45: 300,
    46: 300,
    47: 295,
    # 第48回は区割り後。手元SH-D/MICいずれも289（旧文献の290想定とは1差）
    48: 289,
}


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main() -> None:
    if not SILVER.is_file():
        raise SystemExit(f"missing silver: {SILVER}")
    records = load_jsonl(SILVER)
    bronze_n = sum(1 for _ in BRONZE.open(encoding="utf-8")) if BRONZE.is_file() else 0

    by_th = Counter(r["election_th"] for r in records)
    lines: list[str] = []
    lines.append("# 政治学会 SH-D Silver 検証レポート")
    lines.append(f"generated_at={datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"silver={SILVER}")
    lines.append(f"bronze_rows={bronze_n} silver_rows={len(records)}")
    lines.append("")
    lines.append("## 1. 選挙区カバレッジ")
    lines.append("| th | year | districts | expected | delta |")
    lines.append("|---:|---:|---:|---:|---:|")
    for th in sorted(by_th):
        year = next((r["election_year"] for r in records if r["election_th"] == th), "")
        n = by_th[th]
        exp = EXPECTED_DISTRICTS.get(th)
        delta = "" if exp is None else n - exp
        lines.append(f"| {th} | {year} | {n} | {exp if exp is not None else '—'} | {delta} |")

    # vote arithmetic
    bad_cand_sum = 0
    bad_muni_len = 0
    null_totals = 0
    empty_party = 0
    party_ok = 0
    block_kana = 0
    for r in records:
        n_cand = int(r.get("n_candidates") or 0)
        totals = []
        for c in r.get("candidates") or []:
            v = c.get("district_total_votes")
            if v is None:
                null_totals += 1
            else:
                totals.append(int(v))
            party = (c.get("party") or "").strip()
            if r["election_th"] >= 46:
                if party:
                    party_ok += 1
                else:
                    empty_party += 1
        block = str(r.get("block") or "")
        if block and all("ァ" <= ch <= "ン" or ch == "ー" or "ぁ" <= ch <= "ん" for ch in block if ch.strip()):
            # rough: still kana-only block names
            if block not in {
                "北海道", "東北", "北関東", "東京", "南関東", "北陸信越",
                "東海", "近畿", "中国", "四国", "九州",
            }:
                block_kana += 1
        for m in r.get("municipalities") or []:
            cv = m.get("candidate_votes") or []
            if len(cv) != n_cand:
                bad_muni_len += 1
        if totals and r.get("valid_votes"):
            # soft check: abs gap note only when large
            s = sum(totals)
            vv = int(r["valid_votes"])
            if vv and abs(s - vv) > 1:
                bad_cand_sum += 1

    lines.append("")
    lines.append("## 2. 内部整合")
    lines.append(f"- candidates.district_total_votes が null: {null_totals}")
    lines.append(f"- municipalities.candidate_votes 長さ不一致: {bad_muni_len}")
    lines.append(f"- sum(candidate votes) と valid_votes の差>1 の選挙区: {bad_cand_sum}")
    lines.append(f"- th>=46 政党補完成功: {party_ok} / 空欄: {empty_party}")
    lines.append(f"- block が漢字11ブロック以外のまま: {block_kana}")

    # MIC compare for overlapping shugiin 44-48
    lines.append("")
    lines.append("## 3. MIC facts 対比（衆44–48・小選挙区 candidate_votes の選挙区数）")
    if FACTS.is_file():
        con = duckdb.connect()
        mic = con.execute(
            f"""
            SELECT election_kaiji AS th,
                   count(DISTINCT (prefecture, district_number)) AS districts,
                   count(*) AS candidate_rows
            FROM read_parquet('{FACTS.as_posix()}')
            WHERE election_id LIKE 'shugiin-%'
              AND contest = 'smd' AND metric = 'candidate_votes'
              AND election_kaiji BETWEEN 44 AND 48
            GROUP BY 1
            ORDER BY 1
            """
        ).fetchall()
        mic_map = {int(th): (int(d), int(c)) for th, d, c in mic}
        lines.append("| th | SH-D districts | MIC districts | MIC candidate_rows |")
        lines.append("|---:|---:|---:|---:|")
        for th in range(44, 49):
            sd = by_th.get(th, 0)
            md, mc = mic_map.get(th, (0, 0))
            lines.append(f"| {th} | {sd} | {md} | {mc} |")
        lines.append("")
        lines.append(
            "注: SH-D は市区町村内訳付きの選挙区集計、MIC は候補者得票行。"
            "件数一致は期待せず、選挙区カバレッジの目安として比較。"
        )
        # Sample vote compare: Hokkaido district 1 top candidate votes if names align is hard;
        # compare district valid_votes vs sum MIC votes for a few districts via district_num only after pref map.
        sample_gaps = []
        # Build SH-D index by (th, district_name)
        shd_valid = {(r["election_th"], r["district_name"]): r.get("valid_votes") for r in records}
        # MIC aggregate by pref+district for th=48
        mic_agg = con.execute(
            f"""
            SELECT election_kaiji, prefecture, district_number,
                   sum(value) AS votes
            FROM read_parquet('{FACTS.as_posix()}')
            WHERE election_id LIKE 'shugiin-%'
              AND contest = 'smd' AND metric = 'candidate_votes'
              AND election_kaiji IN (44, 48)
            GROUP BY 1,2,3
            """
        ).fetchall()
        # Match by constructing names like 北海道1区 from pref+num
        matched = 0
        close = 0
        for th, pref, dist, votes in mic_agg:
            name = f"{pref}{int(dist)}区".replace("県", "").replace("府", "").replace("都", "")
            # try several name forms
            candidates = [
                f"{pref}{int(dist)}区",
                f"{str(pref).replace('都','').replace('府','').replace('県','')}{int(dist)}区",
            ]
            vv = None
            for nm in candidates:
                if (int(th), nm) in shd_valid:
                    vv = shd_valid[(int(th), nm)]
                    break
            if vv is None:
                continue
            matched += 1
            if abs(int(vv) - int(votes)) <= 1:
                close += 1
            elif abs(int(vv) - int(votes)) > 50:
                sample_gaps.append((int(th), pref, int(dist), int(vv), int(votes)))
        lines.append("")
        lines.append("## 4. MIC 得票合計との突合（氏名突合なし・選挙区キー）")
        lines.append(f"- 名前キーで突合できた選挙区: {matched}")
        lines.append(f"- |SH-D valid_votes − MIC候補合計| ≤ 1: {close}")
        lines.append(f"- 差>50 の例（最大10）:")
        for row in sample_gaps[:10]:
            lines.append(f"  - th={row[0]} {row[1]} {row[2]}区 SH-D={row[3]} MIC_sum={row[4]} delta={row[3]-row[4]}")
        if not sample_gaps:
            lines.append("  - (なし or 突合不足)")
    else:
        lines.append("(facts.parquet なし — MIC 対比スキップ)")

    lines.append("")
    lines.append("## 5. 判定")
    issues = []
    for th, exp in EXPECTED_DISTRICTS.items():
        if by_th.get(th, 0) != exp:
            issues.append(f"th={th} districts={by_th.get(th,0)} expected={exp}")
    if null_totals:
        issues.append(f"null district_total_votes={null_totals}")
    if empty_party:
        issues.append(f"empty party (th>=46)={empty_party}")
    if issues:
        lines.append("WARN:")
        for i in issues:
            lines.append(f"- {i}")
        lines.append(
            "SH-D Silver は二次ソースとして利用可。倉庫接続は source_code=seiji-gakkai-* で opt-in。"
        )
    else:
        lines.append("OK: 想定選挙区数・政党補完・票フィールドに重大欠損なし。")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    report = OUT_DIR / f"{stamp}_sh_d_silver_verify.txt"
    latest = OUT_DIR / "sh_d_silver_verify.txt"
    text = "\n".join(lines) + "\n"
    report.write_text(text, encoding="utf-8")
    latest.write_text(text, encoding="utf-8")
    # also mirror under seiji-gakkai
    mirror = REPO / "references" / "seiji-gakkai" / "02-silver" / "1996-2017" / "03-SH-D" / "VERIFY.md"
    mirror.parent.mkdir(parents=True, exist_ok=True)
    mirror.write_text(text, encoding="utf-8")
    print(text)
    print(f"wrote {report}")
    print(f"wrote {mirror}")


if __name__ == "__main__":
    main()
