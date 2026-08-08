# v1.0: 第48回の都道府県別得票合計と有効投票の差を確認
import sys
from pathlib import Path
from collections import defaultdict
import duckdb

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from test_parse_03_13 import parse_kaiji

facts = parse_kaiji(48)
votes = defaultdict(float)
for f in facts:
    votes[f["prefecture"]] += float(f["value"])

con = duckdb.connect()
ballots = con.execute(
    """
    SELECT prefecture, max(value) AS valid_votes
    FROM read_parquet(?)
    WHERE election_kaiji=48 AND source_code='03-08' AND metric='valid_ballots'
      AND prefecture NOT IN ('計','合計')
    GROUP BY 1
    """,
    [str(ROOT / "data/warehouse/parquet/facts.parquet")],
).fetchall()
bad = []
for pref, valid in ballots:
    got = votes.get(pref, 0)
    if abs(got - valid) > 1:
        bad.append((pref, valid, got, got - valid))
print("mismatches", len(bad))
for row in sorted(bad, key=lambda x: abs(x[3]), reverse=True)[:15]:
    print(row)
print("national cand", sum(votes.values()), "national valid", sum(v for _, v in ballots))
