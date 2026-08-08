# v1.0: 既存warehouseの第44回と新パーサ結果を比較
import sys
from pathlib import Path
from collections import defaultdict
import duckdb

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from test_parse_03_13 import parse_kaiji

con = duckdb.connect()
old = con.execute(
    """
    SELECT prefecture, sum(value) AS votes, count(*) AS n
    FROM read_parquet(?)
    WHERE metric='candidate_votes' AND election_kaiji=44
    GROUP BY 1 ORDER BY 1
    """,
    [str(ROOT / "data/warehouse/parquet/facts.parquet")],
).fetchall()
old_map = {r[0]: (r[1], r[2]) for r in old}

new = parse_kaiji(44)
new_map = defaultdict(lambda: [0.0, 0])
for f in new:
    new_map[f["prefecture"]][0] += float(f["value"])
    new_map[f["prefecture"]][1] += 1

diffs = []
for pref in sorted(set(old_map) | set(new_map)):
    ov, on = old_map.get(pref, (0, 0))
    nv, nn = new_map.get(pref, [0, 0])
    if abs(ov - nv) > 0.1 or on != nn:
        diffs.append((pref, on, nn, ov, nv, nv - ov))
print("pref diffs", len(diffs))
for row in diffs[:20]:
    print(row)
print("old total", sum(v for v, _ in old_map.values()), sum(n for _, n in old_map.values()))
print("new total", sum(v for v, _ in new_map.values()), sum(n for _, n in new_map.values()))
