# Warehouseの生成と利用

## 生成

```powershell
python .\src\build_election_warehouse.py
```

既定では第44～51回を読み、次を生成する。

```text
data/warehouse/
  soumu_election.duckdb
  manifest.json
  parquet/
    elections.parquet
    source_documents.parquet
    normalization_coverage.parquet
    facts.parquet
    validation_results.parquet
```

対象回や出力先を変える場合:

```powershell
python .\src\build_election_warehouse.py --kaiji 49 50 51 --output .\data\warehouse_recent
```

## SQL例

Pythonから接続する。

```python
import duckdb

con = duckdb.connect("data/warehouse/soumu_election.duckdb", read_only=True)

# 選挙回別のfact件数
print(con.sql("""
    SELECT election_kaiji, count(*) AS facts
    FROM facts
    GROUP BY election_kaiji
    ORDER BY election_kaiji
"""))

# 北海道の国民審査結果
print(con.sql("""
    SELECT election_kaiji, justice, dismissal_yes, dismissal_no
    FROM judicial_review_results
    WHERE prefecture_code = '01'
    ORDER BY election_kaiji, justice
"""))
```

ParquetはDBなしでも直接検索できる。

```sql
SELECT election_kaiji, metric, sum(value)
FROM read_parquet('data/warehouse/parquet/facts.parquet')
GROUP BY election_kaiji, metric;
```

## 主なテーブル

- `facts`: 全選挙回を統合したlong形式の値と出典座標
- `elections`: 選挙回・投票日
- `source_documents`: 総務省資料のURL・ファイル
- `normalization_coverage`: 資料別の正規化状況
- `validation_results`: ビルド時の品質検証
- `judicial_review_results`: 国民審査を分析しやすく横持ちにしたビュー

`facts.source_id` から `source_documents` を結合できる。`raw_only` の資料は `normalization_coverage` で確認する。

## 再現性

`fact_id` と `source_id` は出典座標等から決定的に生成する。再生成しても同じ入力には同じIDが付く。`manifest.json` は対象選挙回、件数、検証結果を記録する。
