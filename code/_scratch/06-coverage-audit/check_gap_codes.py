import duckdb

c = duckdb.connect()
facts = "C:/Users/SKBNW/Documents/Github/soumu-election/data/warehouse/parquet/facts.parquet"
print(
    c.sql(
        f"""
        SELECT election_kaiji, source_code, count(*) AS n
        FROM read_parquet('{facts}')
        WHERE source_code IN ('03-11','03-15','03-16','04-01')
        GROUP BY 1,2 ORDER BY 1,2
        """
    )
)
print(
    c.sql(
        f"""
        SELECT election_kaiji, count(*) AS n
        FROM read_parquet('{facts}')
        GROUP BY 1 ORDER BY 1
        """
    )
)
