# v1.1: 03-07 複数行と小数の内訳
import duckdb

c = duckdb.connect()
facts = r"C:/Users/SKBNW/Documents/Github/soumu-election/data/warehouse/parquet/facts.parquet"

print("=== all 03-07 rows Hokkaido CDP/NDP kaiji 50 ===")
print(c.sql(f"""
SELECT party, pr_block, value, source_cell, source_sheet
FROM read_parquet('{facts}')
WHERE election_kaiji=50 AND source_code='03-07' AND prefecture='北海道'
  AND party IN ('立憲民主党','国民民主党','合計')
ORDER BY party, CAST(regexp_extract(source_cell, '(\\d+)', 1) AS INT)
"""))

print("\n=== party names in 03-07 header kaiji 50 ===")
print(c.sql(f"""
SELECT DISTINCT party FROM read_parquet('{facts}')
WHERE election_kaiji=50 AND source_code='03-07'
ORDER BY 1
"""))

print("\n=== 03-10 Hokkaido block kaiji 50 ===")
print(c.sql(f"""
SELECT party, metric, value, unit
FROM read_parquet('{facts}')
WHERE election_kaiji=50 AND source_code='03-10'
  AND replace(pr_block,'選挙区','')='北海道'
  AND party IN ('立憲民主党','国民民主党')
ORDER BY party, metric
"""))

print("\n=== national 03-07 rows kaiji 50 ===")
print(c.sql(f"""
SELECT party, value, source_cell
FROM read_parquet('{facts}')
WHERE election_kaiji=50 AND source_code='03-07' AND pr_block='全国'
  AND party IN ('立憲民主党','国民民主党')
ORDER BY party, value DESC
"""))

# What does arg_min pick?
print("\n=== simulate UI prefecture query ===")
print(c.sql(f"""
SELECT election_kaiji, replace(pr_block, '選挙区', '') AS pr_block,
       prefecture, party,
       arg_min(value, CAST(regexp_extract(source_cell, '(\\d+)', 1) AS INTEGER)) AS value_first_cell,
       min(value) AS min_v, max(value) AS max_v, count(*) AS n
FROM read_parquet('{facts}')
WHERE metric='party_votes' AND source_code='03-07' AND election_kaiji=50
  AND prefecture='北海道' AND party IN ('立憲民主党','国民民主党')
GROUP BY 1,2,3,4
"""))
