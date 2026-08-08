# v1.0: candidate_votes と有効投票の不一致を選挙回・都道府県別に列挙
from pathlib import Path
import duckdb

path = Path("data/warehouse/parquet/facts.parquet")
con = duckdb.connect()
rows = con.execute(
    """
    WITH candidates AS (
      SELECT election_kaiji, prefecture, sum(value) AS votes
      FROM read_parquet(?)
      WHERE metric='candidate_votes'
      GROUP BY 1,2
    ), ballots AS (
      SELECT election_kaiji, prefecture, max(value) AS valid_votes
      FROM read_parquet(?)
      WHERE source_code='03-08' AND metric='valid_ballots'
        AND prefecture NOT IN ('計','合計')
      GROUP BY 1,2
    )
    SELECT c.election_kaiji, c.prefecture, b.valid_votes, c.votes, c.votes - b.valid_votes AS diff
    FROM candidates c
    JOIN ballots b USING (election_kaiji, prefecture)
    WHERE abs(c.votes - b.valid_votes) > 0.1
    ORDER BY 1, abs(diff) DESC
    """,
    [str(path), str(path)],
).fetchall()
print("failures", len(rows))
for row in rows:
    print(row)
