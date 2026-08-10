# -*- coding: utf-8 -*-
"""
enrich_seiji_gakkai_smd_district_outcome_v1.0.py
- v1.0.1: absolute_vote_rate を％へ正規化（CAN 42–45 は割合 0–1）
- CAN の vote_rank / absolute_vote_rate / sekihairitsu を付与
- SH-B の is_pr_winner を付与（比例復活）
- MIC facts には触れない（seiji parquet のみ更新）
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parents[2]
CAN = REPO / "references/seiji-gakkai/01-bronze/1996-2017/01-CAN/can-candidates.jsonl"
SHB = REPO / "references/seiji-gakkai/01-bronze/1996-2017/04-SH-B/shb-candidates.jsonl"
DIST = REPO / "data/warehouse/parquet/seiji_gakkai_smd_district_votes.parquet"
WEB = REPO / "web/data/seiji_gakkai_smd_district_votes.parquet"
OUT_DIR = REPO / "output/04-seiji-gakkai"


def nfkc(s):
    import unicodedata
    return unicodedata.normalize("NFKC", str(s or "").strip())


def load_can():
    by = {}
    with CAN.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            key = (int(r["election_th"]), int(r["district_num"]), nfkc(r.get("name_kana")))
            by[key] = r
    return by


def load_shb_pr_winners():
    winners = set()
    with SHB.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("is_pr_winner") is True:
                winners.add((int(r["election_th"]), nfkc(r.get("name_kana")), nfkc(r.get("party_name"))))
    return winners


def normalize_absolute_vote_rate(abs_rate, votes, eligible):
    """CAN の absolute_vote_rate をパーセントに揃える（42–45 は割合 0–1）。"""
    if abs_rate is None:
        return None
    try:
        rate = float(abs_rate)
    except (TypeError, ValueError):
        return abs_rate
    if eligible and votes is not None and float(eligible) > 0:
        calc = 100.0 * float(votes) / float(eligible)
        if abs(calc - rate * 100.0) < abs(calc - rate):
            return round(rate * 100.0, 6)
        return rate
    return rate


def main():
    can = load_can()
    pr_winners = load_shb_pr_winners()
    con = duckdb.connect()
    src = DIST if DIST.is_file() else WEB
    cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{src.as_posix()}')").fetchall()]
    raw = con.execute(f"SELECT * FROM read_parquet('{src.as_posix()}')").fetchall()
    rows = [dict(zip(cols, tup)) for tup in raw]
    matched_can = 0
    matched_pr = 0
    for row in rows:
        key = (int(row["election_kaiji"]), int(row["district_number"]), nfkc(row.get("candidate")))
        c = can.get(key)
        vote_rank = c.get("vote_rank") if c else None
        abs_rate = normalize_absolute_vote_rate(
            c.get("absolute_vote_rate") if c else None,
            row.get("value"),
            row.get("district_eligible_voters"),
        )
        seki = c.get("sekihairitsu") if c else None
        if c:
            matched_can += 1
        party = nfkc(row.get("party"))
        is_pr = (int(row["election_kaiji"]), nfkc(row.get("candidate")), party) in pr_winners
        if is_pr:
            matched_pr += 1
        elected_smd = True if vote_rank == 1 else (False if vote_rank is not None else None)
        if elected_smd is None and row.get("value") is not None:
            # fallback later via SQL window if needed
            pass
        if elected_smd:
            outcome = "smd"
            outcome_label = "当選（小）"
        elif is_pr:
            outcome = "pr"
            outcome_label = "比例復活"
        elif elected_smd is False:
            outcome = "loss"
            outcome_label = "落選"
        else:
            outcome = None
            outcome_label = None
        row["vote_rank"] = vote_rank
        row["absolute_vote_rate"] = abs_rate
        row["sekihairitsu"] = seki
        row["elected_smd"] = elected_smd
        row["is_pr_winner"] = is_pr
        row["outcome"] = outcome
        row["outcome_label"] = outcome_label

    # fill elected_smd by max votes when CAN miss
    by_dist = defaultdict(list)
    for row in rows:
        by_dist[(row["election_kaiji"], row["prefecture"], row["district_number"])].append(row)
    for group in by_dist.values():
        vals = [r["value"] for r in group if r.get("value") is not None]
        if not vals:
            continue
        top = max(vals)
        for r in group:
            if r.get("elected_smd") is not None:
                continue
            if r.get("value") == top:
                r["elected_smd"] = True
                r["outcome"] = "smd"
                r["outcome_label"] = "当選（小）"
            else:
                r["elected_smd"] = False
                if r.get("is_pr_winner"):
                    r["outcome"] = "pr"
                    r["outcome_label"] = "比例復活"
                else:
                    r["outcome"] = "loss"
                    r["outcome_label"] = "落選"

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    staging = OUT_DIR / f"{stamp}_seiji_smd_district_enriched.jsonl"
    with staging.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            # numpy types → plain
            clean = {}
            for k, v in row.items():
                if hasattr(v, "item"):
                    try:
                        v = v.item()
                    except Exception:
                        pass
                if v != v:  # NaN
                    v = None
                clean[k] = v
            f.write(json.dumps(clean, ensure_ascii=False) + "\n")

    DIST.parent.mkdir(parents=True, exist_ok=True)
    WEB.parent.mkdir(parents=True, exist_ok=True)
    con.execute(
        f"""
        COPY (
          SELECT * FROM read_json_auto('{staging.as_posix()}')
          ORDER BY election_kaiji, prefecture_code NULLS LAST, district_number, list_position
        ) TO '{DIST.as_posix()}' (FORMAT PARQUET)
        """
    )
    WEB.write_bytes(DIST.read_bytes())
    report = OUT_DIR / f"{stamp}_district_outcome_enrich_report.txt"
    report.write_text(
        "\n".join(
            [
                f"rows={len(rows)}",
                f"matched_can={matched_can}",
                f"matched_pr_winner={matched_pr}",
                f"out={DIST}",
            ]
        ),
        encoding="utf-8",
    )
    print(report.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
