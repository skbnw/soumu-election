# v1.0: municipality_facts の subject/party 空白除去
from pathlib import Path
import duckdb

ROOT = Path(r"C:\Users\SKBNW\Documents\Github\soumu-election")
con = duckdb.connect()
for rel in (
    ROOT / "data/warehouse/parquet/municipality_facts.parquet",
    ROOT / "web/data/municipality_facts.parquet",
):
    tmp = rel.with_suffix(".tmp.parquet")
    con.execute(f"""
        COPY (
          SELECT * REPLACE (
            CASE WHEN subject IS NULL THEN NULL
                 ELSE replace(replace(subject, ' ', ''), chr(12288), '') END AS subject,
            CASE WHEN party IS NULL THEN NULL
                 ELSE replace(replace(party, ' ', ''), chr(12288), '') END AS party,
            CASE WHEN candidate IS NULL THEN NULL
                 ELSE replace(replace(candidate, ' ', ''), chr(12288), '') END AS candidate
          )
          FROM read_parquet('{rel.as_posix()}')
        ) TO '{tmp.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    tmp.replace(rel)
    print("ok", rel)

print(con.sql(f"""
SELECT
  count(*) FILTER (WHERE subject LIKE '% %' OR subject LIKE '%'||chr(12288)||'%') AS subject_spaced,
  count(*) FILTER (WHERE party LIKE '% %' OR party LIKE '%'||chr(12288)||'%') AS party_spaced
FROM read_parquet('{(ROOT / 'web/data/municipality_facts.parquet').as_posix()}')
"""))
print(con.sql(f"""
SELECT DISTINCT subject, party
FROM read_parquet('{(ROOT / 'web/data/municipality_facts.parquet').as_posix()}')
WHERE subject LIKE '%みたぞ%' OR subject LIKE '%民主%'
ORDER BY 1 LIMIT 15
"""))
