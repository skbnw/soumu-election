# -*- coding: utf-8 -*-
"""
verify_historical_mmd_silver_v1.0.py
- 政治学会・中選挙区（1958–1993 / HR-28–40）historical Silver の検証
- 小選挙区（1996–）レイヤとは混ぜない前提の健全性チェック
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HIST = REPO / "references" / "seiji-gakkai" / "02-silver" / "historical"
OUT_DIR = REPO / "output" / "04-seiji-gakkai"

EXPECTED_ELECTIONS = [
    (28, 1958), (29, 1960), (30, 1963), (31, 1967), (32, 1969),
    (33, 1972), (34, 1976), (35, 1979), (36, 1980), (37, 1983),
    (38, 1986), (39, 1990), (40, 1993),
]


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main() -> None:
    elections = load_jsonl(HIST / "elections.jsonl")
    candidates = load_jsonl(HIST / "candidates.jsonl")
    districts = load_jsonl(HIST / "districts.jsonl")
    results = load_jsonl(HIST / "results.jsonl")
    detail_path = HIST / "snk_tokuhyo_detail.jsonl"
    detail_n = sum(1 for _ in detail_path.open(encoding="utf-8")) if detail_path.is_file() else 0

    lines: list[str] = []
    lines.append("# 政治学会 中選挙区（historical / MMD）Silver 検証レポート")
    lines.append(f"generated_at={datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"path={HIST}")
    lines.append("")
    lines.append("## 方針")
    lines.append("- 制度: 中選挙区（system=MMD）。1996年以降の小選挙区レイヤとは **別系列**。")
    lines.append("- source: `seiji-gakkai` / 将来倉庫接続時は `seiji-gakkai-historical-*`。")
    lines.append("- MIC `facts` や 1996– SH-D Silver へ merge しない。")
    lines.append("- UI: 衆院選/参院選のみ。**中選挙区は当面 Web 非掲載**。")
    lines.append("- 将来公開するなら第3コーナ「衆院選（中選挙区）」のみ（既存衆院選に混ぜない）。")
    lines.append("")

    lines.append("## 1. 収録選挙")
    lines.append("| th | year | election_id | genre | candidates | results |")
    lines.append("|---:|---:|---|---|---:|---:|")
    cand_by = Counter(c["election_id"] for c in candidates)
    res_by = Counter(r["election_id"] for r in results)
    elec_map = {e["election_id"]: e for e in elections}
    for th, year in EXPECTED_ELECTIONS:
        eid = f"HR-{th}"
        e = elec_map.get(eid, {})
        lines.append(
            f"| {th} | {year} | {eid} | {e.get('genre','')} | "
            f"{cand_by.get(eid,0)} | {res_by.get(eid,0)} |"
        )

    issues: list[str] = []
    for th, year in EXPECTED_ELECTIONS:
        eid = f"HR-{th}"
        if eid not in elec_map:
            issues.append(f"missing election {eid}")
            continue
        if elec_map[eid].get("year") != year:
            issues.append(f"{eid} year={elec_map[eid].get('year')} expected={year}")
        if elec_map[eid].get("genre") != "HR-Historical":
            issues.append(f"{eid} genre={elec_map[eid].get('genre')}")
        if cand_by.get(eid, 0) != res_by.get(eid, 0):
            issues.append(f"{eid} candidates≠results")

    systems = Counter(d.get("system") for d in districts)
    lines.append("")
    lines.append("## 2. スキーマ・参照整合")
    lines.append(f"- elections={len(elections)} candidates={len(candidates)} "
                 f"districts={len(districts)} results={len(results)} "
                 f"snk_tokuhyo_detail={detail_n}")
    lines.append(f"- districts.system={dict(systems)}")
    lines.append(f"- candidates.source={dict(Counter(c.get('source') for c in candidates))}")
    lines.append(f"- results.source={dict(Counter(r.get('source') for r in results))}")

    cid = {c["candidate_id"] for c in candidates}
    rid = {r["candidate_id"] for r in results}
    did = {d["district_id"] for d in districts}
    cdid = {c["district_id"] for c in candidates}
    if cid - rid:
        issues.append(f"candidates without results: {len(cid - rid)}")
    if rid - cid:
        issues.append(f"results without candidates: {len(rid - cid)}")
    if cdid - did:
        issues.append(f"candidate district_id missing in districts: {len(cdid - did)}")
    if systems and set(systems) != {"MMD"}:
        issues.append(f"unexpected district systems: {dict(systems)}")

    # elected counts sanity
    elected_by = Counter(
        r["election_id"] for r in results if r.get("elected") is True
    )
    lines.append("")
    lines.append("## 3. 当選者数（elected=true）")
    lines.append("| election_id | elected | candidates |")
    lines.append("|---|---:|---:|")
    for th, _year in EXPECTED_ELECTIONS:
        eid = f"HR-{th}"
        lines.append(f"| {eid} | {elected_by.get(eid,0)} | {cand_by.get(eid,0)} |")

    # name quality note
    kana_like = sum(
        1 for c in candidates
        if c.get("name") and all(
            ("ァ" <= ch <= "ン") or ("ｧ" <= ch <= "ﾝ") or ch in "ー･・ "
            or ("ｱ" <= ch <= "ﾝ")
            for ch in str(c["name"])
        )
    )
    lines.append("")
    lines.append("## 4. 氏名品質（参考）")
    lines.append(f"- 候補者名がカタカナ主体と推定: {kana_like} / {len(candidates)}")
    lines.append("- 表示時は漢字正本（読売・白書・MIC）との突合が別途必要。historical 層ではカナ名を許容。")

    lines.append("")
    lines.append("## 5. 判定")
    if issues:
        lines.append("WARN:")
        for i in issues:
            lines.append(f"- {i}")
    else:
        lines.append(
            "OK: HR-28–40・MMD 別系列として参照整合が取れている。"
            "小選挙区 Silver / MIC facts とは混在させない。"
        )

    text = "\n".join(lines) + "\n"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    report = OUT_DIR / f"{stamp}_historical_mmd_silver_verify.txt"
    latest = OUT_DIR / "historical_mmd_silver_verify.txt"
    mirror = HIST / "VERIFY.md"
    report.write_text(text, encoding="utf-8")
    latest.write_text(text, encoding="utf-8")
    mirror.write_text(text, encoding="utf-8")
    print(text)
    print(f"wrote {report}")
    print(f"wrote {mirror}")


if __name__ == "__main__":
    main()
