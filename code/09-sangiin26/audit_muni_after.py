#!/usr/bin/env python3
"""Confirm municipality district-suffix spellings are unified."""
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
      AND (municipality LIKE '%(%' OR municipality LIKE '%（%')
    GROUP BY 1, 2
    ORDER BY 2, 1
    """
).fetchall()

# remaining non-canonical forms
bad = []
for kaiji, name, c in rows:
    if re.search(r"[（(][0-9０-９]+区[）)]$", name or ""):
        if not re.search(r"（[0-9]+区）$", name):
            bad.append((kaiji, name, c))

print("non_canonical", len(bad))
for item in bad[:30]:
    print(" ", item)

# same base+district with multiple spellings should be gone
by_key: dict[tuple[str, str], set[str]] = defaultdict(set)
for kaiji, name, c in rows:
    m = re.search(r"^(.*?)[（(]([0-9０-９]+)区[）)]$", name or "")
    if not m:
        continue
    base, digits = m.group(1), m.group(2)
    by_key[(base.rstrip("第"), digits.translate(str.maketrans("０１２３４５６７８９", "0123456789")))].add(name)

multi = {k: v for k, v in by_key.items() if len(v) > 1}
print("duplicate_spellings_for_same_district", len(multi))
for k, v in list(sorted(multi.items()))[:10]:
    print(k, v)

print("sapporo nishi:")
for kaiji, name, c in rows:
    if "札幌市西区" in name:
        print(kaiji, name, c)
