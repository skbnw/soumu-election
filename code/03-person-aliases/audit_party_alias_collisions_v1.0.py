# -*- coding: utf-8 -*-
"""Scan party aliases for same-election collisions (alias and distinct short both present)."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parents[2]
WEB = REPO / "web" / "data"
OUT = REPO / "output" / "03-person-aliases"


def main() -> None:
    con = duckdb.connect()
    aliases = con.execute(
        f"""
        SELECT election_kaiji, alias_name, canonical_name, match_method
        FROM read_parquet('{(WEB / "party_name_aliases.parquet").as_posix()}')
        """
    ).fetchall()

    # global maps
    global_map = {a: c for k, a, c, m in aliases if k is None}
    by_kaiji: dict[int, dict[str, str]] = defaultdict(dict)
    for k, a, c, m in aliases:
        if k is not None:
            by_kaiji[int(k)][a] = c

    pr = (WEB / "seiji_gakkai_pr_votes.parquet").as_posix()
    parties = con.execute(
        f"""
        SELECT election_kaiji, party, geo_level, sum(value) AS votes
        FROM read_parquet('{pr}')
        WHERE metric='party_votes' AND coalesce(party,'') NOT IN ('','合計','計')
        GROUP BY 1,2,3
        """
    ).fetchall()

    # per kaiji set of raw party names (any geo)
    raw_by: dict[int, set[str]] = defaultdict(set)
    votes_nat: dict[tuple[int, str], int] = {}
    for th, party, geo, votes in parties:
        raw_by[int(th)].add(party)
        if geo == "national":
            votes_nat[(int(th), party)] = int(votes or 0)

    def canon(th: int, name: str) -> str:
        return by_kaiji.get(th, {}).get(name) or global_map.get(name) or name

    collisions = []
    for th, names in sorted(raw_by.items()):
        # group by displayed canonical
        groups: dict[str, list[str]] = defaultdict(list)
        for n in sorted(names):
            groups[canon(th, n)].append(n)
        for cname, members in groups.items():
            if len(set(members)) >= 2:
                detail = [
                    (m, votes_nat.get((th, m)), "national" if (th, m) in votes_nat else "block-only")
                    for m in members
                ]
                collisions.append((th, cname, detail))

    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"{stamp}_party_alias_collision_audit.txt"
    lines = [
        "# party alias collision audit (seiji PR)",
        f"generated_at={datetime.now().isoformat(timespec='seconds')}",
        "rule: same election_kaiji, 2+ distinct raw party names share one canonical display",
        f"collisions={len(collisions)}",
        "",
    ]
    for th, cname, detail in collisions:
        lines.append(f"## th={th} canonical={cname}")
        for m, v, g in detail:
            lines.append(f"  raw={m}\tnational_votes={v}\t{g}")
        lines.append("")

    if not collisions:
        lines.append("(none)")

    text = "\n".join(lines) + "\n"
    out.write_text(text, encoding="utf-8")
    (OUT / "party_alias_collision_audit.txt").write_text(text, encoding="utf-8")
    print(text)
    print("wrote", out)


if __name__ == "__main__":
    main()
