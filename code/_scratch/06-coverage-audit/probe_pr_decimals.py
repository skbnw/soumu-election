# v1.0: 比例03-07異常値と市町村名空白の調査
import duckdb

c = duckdb.connect()
facts = r"C:/Users/SKBNW/Documents/Github/soumu-election/data/warehouse/parquet/facts.parquet"
muni = r"C:/Users/SKBNW/Documents/Github/soumu-election/data/warehouse/parquet/municipality_facts.parquet"

print("=== 03-07 sample Hokkaido CDP kaiji 49-50 ===")
print(c.sql(f"""
SELECT election_kaiji, source_code, contest, prefecture, pr_block, party,
       metric, unit, value, gender, age_band, row_variant, source_file, source_cell
FROM read_parquet('{facts}')
WHERE election_kaiji IN (49,50)
  AND source_code='03-07'
  AND prefecture='北海道'
  AND party LIKE '%立憲%'
ORDER BY election_kaiji, metric, value DESC
LIMIT 40
"""))

print("\n=== distinct metrics in 03-07 ===")
print(c.sql(f"""
SELECT election_kaiji, metric, unit, count(*) n,
       sum(CASE WHEN value != trunc(value) THEN 1 ELSE 0 END) AS fractional,
       min(value) mn, max(value) mx
FROM read_parquet('{facts}')
WHERE source_code='03-07' AND election_kaiji IN (49,50)
GROUP BY 1,2,3 ORDER BY 1,2
"""))

print("\n=== compare 03-05 / 03-07 / 03-10 for Hokkaido parties kaiji 50 ===")
print(c.sql(f"""
SELECT source_code, pr_block, prefecture, party, metric, value, unit
FROM read_parquet('{facts}')
WHERE election_kaiji=50
  AND source_code IN ('03-05','03-07','03-10')
  AND party IN ('立憲民主党','国民民主党')
  AND (prefecture='北海道' OR prefecture IS NULL OR prefecture IN ('計','合計','全国') OR pr_block='北海道')
ORDER BY source_code, party, prefecture, pr_block, metric
"""))

print("\n=== municipality names with spaces ===")
print(c.sql(f"""
SELECT election_kaiji, contest, prefecture, municipality, length(municipality) AS len,
       count(*) n
FROM read_parquet('{muni}')
WHERE municipality IS NOT NULL
  AND (municipality != replace(replace(municipality, ' ', ''), '　', '')
       OR municipality != trim(municipality)
       OR municipality LIKE '% %'
       OR municipality LIKE '%　%')
GROUP BY 1,2,3,4
ORDER BY 1 DESC, 4
LIMIT 40
"""))
print(c.sql(f"""
SELECT count(*) AS spaced_names,
       count(DISTINCT municipality) AS distinct_spaced
FROM read_parquet('{muni}')
WHERE municipality IS NOT NULL
  AND (municipality LIKE '% %' OR municipality LIKE '%　%' OR municipality != trim(municipality))
"""))
