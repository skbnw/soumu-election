# v1.0: 市町村名空白のみ修正
from pathlib import Path
import duckdb

ROOT = Path(r"C:\Users\SKBNW\Documents\Github\soumu-election")
con = duckdb.connect()
for rel in (
    ROOT / "data/warehouse/parquet/municipality_facts.parquet",
    ROOT / "web/data/municipality_facts.parquet",
    ROOT / "data/warehouse/parquet/smd_municipality_votes.parquet",
    ROOT / "web/data/smd_municipality_votes.parquet",
):
    if not rel.exists():
        continue
    tmp = rel.with_suffix(".tmp.parquet")
    con.execute(f"""
        COPY (
          SELECT * REPLACE (
            CASE WHEN municipality IS NULL THEN NULL
                 ELSE replace(replace(municipality, ' ', ''), chr(12288), '')
            END AS municipality
          )
          FROM read_parquet('{rel.as_posix()}')
        ) TO '{tmp.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    tmp.replace(rel)
    print("ok", rel)

p = ROOT / "web/data/municipality_facts.parquet"
print(con.sql(f"""
SELECT count(*) AS still_spaced,
       count(*) FILTER (WHERE municipality = 'みどり市') AS midori,
       count(*) FILTER (WHERE municipality = 'み ど り 市') AS midori_spaced
FROM read_parquet('{p.as_posix()}')
WHERE municipality IS NOT NULL
"""))
print(con.sql(f"""
SELECT election_kaiji, party, value
FROM read_parquet('{(ROOT / 'web/data/facts.parquet').as_posix()}')
WHERE election_kaiji=50 AND source_code='03-07' AND prefecture='北海道'
  AND party IN ('立憲民主党','国民民主党','れいわ新選組','社会民主党')
ORDER BY party
"""))
