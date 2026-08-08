#!/usr/bin/env python3
"""Audit shugiin municipality name variants with district suffixes."""
from __future__ import annotations

import re
from collections import defaultdict

import duckdb

con = duckdb.connect()
rows = con.execute(
    """
    SELECT election_kaiji, municipality, count(*) AS c
    FROM read_parquet('web/data/municipality_facts.parquet')
    WHERE (chamber IS NULL OR chamber = 'shugiin')
      AND municipality IS NOT NULL
      AND (
        municipality LIKE '%(%'
        OR municipality LIKE '%（%'
        OR municipality LIKE '%区）%'
        OR municipality LIKE '%区)%'
      )
    GROUP BY 1, 2
    ORDER BY 2, 1
    """
).fetchall()

print("rows_with_paren_marker", len(rows))
by_base: dict[str, set[str]] = defaultdict(set)
samples = []
for kaiji, name, c in rows:
    samples.append((kaiji, name, c))
    # strip trailing （N区） / (N区)
    base = re.sub(r"[（(][0-9０-９]+区[）)]\s*$", "", name)
    by_base[base].add(name)

multi = {k: sorted(v) for k, v in by_base.items() if len(v) > 1}
print("bases_with_multiple_spellings", len(multi))
for i, (base, variants) in enumerate(sorted(multi.items())[:40]):
    print(f"  {base!r}: {variants}")

# char-class inventory
half = [r for r in samples if re.search(r"\([0-9]+区\)", r[1])]
full = [r for r in samples if re.search(r"（[０-９]+区）", r[1])]
mixed1 = [r for r in samples if re.search(r"（[0-9]+区）", r[1])]
mixed2 = [r for r in samples if re.search(r"\([０-９]+区\)", r[1])]
print("half_ascii_digits", len(half), "sample", half[:5])
print("full_zenkaku", len(full), "sample", full[:5])
print("full_paren_ascii_digits", len(mixed1), "sample", mixed1[:5])
print("half_paren_zenkaku_digits", len(mixed2), "sample", mixed2[:5])

# kaiji coverage for Sapporo Nishi
print("\n札幌市西区 variants:")
for kaiji, name, c in samples:
    if "札幌市西区" in name:
        print(kaiji, name, c)
