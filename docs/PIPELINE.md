# データ処理パイプライン（公開向け）

最終更新: 2026-08-08

総務省の衆院選ページから取得し、分析用warehouseとGitHub Pages用データまで進む**標準の一本道**です。  
参院（`sangiin`）は同一構成で後続拡張する予定です（`DATASET_PLAN.md` 9章）。

## 全体像

```text
総務省 Web（衆院選 index / 市区町村別）
    │  1. download
    ▼
data/shugiin{回}/raw + raw_json + smd_votes.json + pr_votes.json
    │  2. normalize
    ▼
data/shugiin{回}/normalized/facts.json
    │  3. warehouse
    ▼
data/warehouse/{soumu_election.duckdb, parquet/*.parquet, manifest.json}
    │  4. municipality
    ▼
data/warehouse/parquet/municipality_facts.parquet
（web/data へもコピー）
    │  main へ push
    ▼
GitHub Pages（web/ + warehouse parquet）
```

## セットアップ

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

作業ディレクトリはリポジトリルートにしてください。

## いちばん簡単な実行（推奨）

既に `data/shugiin*` がある場合（再取得しない）:

```powershell
.\.venv\Scripts\python.exe .\src\run_pipeline.py `
  --project-root . `
  --steps normalize,warehouse,municipality
```

取得からやり直す場合（時間がかかります。総務省へアクセスします）:

```powershell
.\.venv\Scripts\python.exe .\src\run_pipeline.py `
  --project-root . `
  --kaiji 51 `
  --steps download,normalize,warehouse,municipality
```

全回（44〜51）を一括する場合は `--kaiji` を省略します。`--force-download` で原本を取り直します。

### ステップだけ実行する例

| 目的 | コマンド |
|------|----------|
| 倉庫だけ再生成 | `--steps warehouse` |
| 市区町村parquetだけ | `--steps municipality` |
| 第51回だけ正規化 | `--kaiji 51 --steps normalize` |

## 個別CLI（中身を触るとき）

| 段階 | エントリ | 実体 |
|------|----------|------|
| 取得 | `src/soumu_shugiin_to_json.py --kaiji N` | `soumu_election.download` |
| 正規化 | `src/normalize_election_facts.py --input ... --output ...` | `soumu_election.normalize` |
| 倉庫 | `src/build_election_warehouse.py` | `soumu_election.warehouse` |
| 市区町村 | `src/build_municipality_facts.py` | `soumu_election.municipality` |
| 一括 | `src/run_pipeline.py` | `soumu_election.pipeline` |

## 成果物の見方

- **分析**: `data/warehouse/soumu_election.duckdb` または `parquet/facts.parquet`（`docs/WAREHOUSE.md`）
- **ブラウザ検索**: `web/`（ローカルなら静的サーバ、公開は Pages）
- **カバレッジ**: 各回 `normalized/manifest.json` と倉庫の `normalization_coverage`

## やらないこと（初心者向け）

- `code/` 配下の `probe_` / `try_` / `peek_` / `diag_` は調査用です。標準パイプラインではありません（`code/README.md`）。
- raw を手で書き換えて「直した」ことにしない。補正は後段処理で行う方針です。
- warehouse の検証が一部 fail でも parquet は書かれることがあります。`manifest.json` の `validation` を確認してください。

## 公開サイトへ反映

1. 上記パイプラインで `data/warehouse/parquet/` を更新
2. 必要なら `web/` のUIも更新
3. `main` へ push → `.github/workflows/pages.yml` が Pages を更新

## 参院（試作）

```powershell
.\.venv\Scripts\python.exe .\src\soumu_shugiin_to_json.py --chamber sangiin --kaiji 27
```

出力は `data/sangiin27/`。当面は raw / raw_json まで（正規化パーサは後続）。Pages の参院タブは建設中表示。
