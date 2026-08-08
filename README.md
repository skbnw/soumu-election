# 総務省・衆議院選挙結果のJSON化

## ブラウザ版

[衆院選データアーカイブ](https://skbnw.github.io/soumu-election/) では、第44〜51回の正規化済みデータを選挙回・都道府県・指標・候補者名等で横断検索できます。DuckDB-Wasmが公開用Parquetをブラウザ内で検索するため、サーバーへ検索条件を送信しません。表示結果はCSVとして保存できます。

サイトは `web/`、公開処理は `.github/workflows/pages.yml` にあります。`data/warehouse/parquet/` を更新してmainブランチへ反映すると、GitHub Pagesも自動更新されます。

総務省の選挙結果indexと「候補者別 市区町村別得票数」ページから全公式Excelを取得します。全セルを汎用raw JSONへ変換するとともに、小選挙区と比例代表の市区町村別得票を分析しやすいJSONへ変換します。Excel原本も保存し、各JSONレコードには出典URL、ファイル名、シート名、Excel行番号を残します。

## 実行

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe .\src\soumu_shugiin_to_json.py --kaiji 51
```

出力先は `data/shugiin51/` です。

- `raw/`: 総務省から取得したExcel・PDF原本。`01-01`、`03-14-smd-01` のような公式項番付きファイル名
- `raw_json/`: Excelの非空セル・セル座標・結合セル情報、およびPDFのページ別抽出テキストを保持したJSON
- `smd_votes.json`: 小選挙区の候補者別・開票区別得票
- `pr_votes.json`: 比例代表の政党別・開票区別得票
- `manifest.json`: 取得元、SHA-256、件数、検証結果

既存の原本は再利用します。総務省側の更新を取り直す場合は `--force` を付けます。別回は `--kaiji` の数字を変えます。ページやExcelの構造が変わった場合は、黙って欠損データを作らず例外終了します。

## データ方針

候補者名は、分析用の空白なし `candidate` と、総務省の表示を保つ `candidate_raw` を併存させます。政党名と開票区名は空白だけ整え、元表記を維持します。人物・政党・自治体の名寄せや公表値の訂正は、raw JSONを上書きせず、後段の補正・正規化処理で行ってください。

`04-01 管理執行上問題となった事項` のように総務省ページ上でリンク先が空の資料は、取得済みを装わず `manifest.json` の `unavailable_sources` に理由とともに記録します。

## ディレクトリ構成

回次ごとにコードを複製せず、共通コードと回次設定を分離します。

```text
src/
  soumu_election/
    download.py             # 全回共通の取得・raw JSON・得票変換
    normalize.py            # 全回共通のsemantic変換
config/
  shugiin44.json            # 第44回。全資料PDF、市区町村別リンクなし
  shugiin45.json            # 第45回。比例資料名の旧表記に対応
  shugiin46.json            # 第46回。リンク表示注記とPDFのみの資料に対応
  shugiin47.json            # 第47回。候補者別得票など一部PDFのみ
  shugiin48.json            # 第48回。旧形式xlsと年齢別投票資料を含む
  shugiin49.json            # 第49回。市区町村別は47サブページ
  shugiin50.json            # 第50回の日付、公式URL、確認済み形式差分
  shugiin51.json            # 第51回の日付、公式URL、確認済み形式差分
data/
  shugiin44/
  shugiin45/
  shugiin46/
  shugiin47/
  shugiin48/
  shugiin49/
  shugiin50/
  shugiin51/
```

`src` 直下の2スクリプトは従来コマンド用の互換ラッパーです。第50回は次の順に実行できます。

```powershell
.\.venv\Scripts\python.exe .\src\soumu_shugiin_to_json.py --kaiji 50
.\.venv\Scripts\python.exe .\src\normalize_election_facts.py `
  --input .\data\shugiin50\raw_json `
  --output .\data\shugiin50\normalized
```

## 分析用normalized層

`src/normalize_election_facts.py` は、`raw_json/` だけを入力として `normalized/facts.json` を生成します。横持ちのExcel表を、`source_code`、`contest`、`prefecture`、`metric`、`gender`、`value`、`unit` などを持つlong形式へ変換します。全レコードに元ファイル・シート・セル座標を残します。

```powershell
.\.venv\Scripts\python.exe .\src\normalize_election_facts.py `
  --input .\data\shugiin51\raw_json `
  --output .\data\shugiin51\normalized
```

`normalized/manifest.json` の `coverage` には、資料ごとに `normalized` または `raw_only` と件数を記録します。未対応表を変換済みとして扱わないための品質管理情報です。

第51回では、全22 Excel集計資料を正規化済みです。`facts.json` に加え、用途別に `candidate_facts.json`、`party_facts.json`、`turnout_facts.json`、`judicial_review_facts.json` を出力します。PDFの表紙・候補者一覧・全体版は、Excelと重複するためraw層に保持します。

主な `metric` は `candidates`、`elected_candidates`、`eligible_voters`、`voters`、`abstentions`、`turnout_rate`、`party_votes`、`current_votes`、`party_vote_share`、`valid_ballots`、`invalid_ballots`、`dismissal_yes`、`dismissal_no`、`dhondt_quotient` です。人数は `people`、票は `votes`、百分率は `percent`、0～1の比率は `ratio` として区別します。

## 古い選挙回とPDF

古い回次では、ExcelがなくPDFだけの場合があります。PDFは原本とページ別抽出テキストを保存しますが、抽出テキストの見た目だけから列対応を推定して自動的にnormalizedへ入れません。表の罫線、複数段見出し、ページ継続、OCR誤りを確認し、回次別の検証済みパーサーまたは補正定義が用意できた資料だけをsemantic変換します。

PDFポートフォリオの場合は、内部の添付ファイルも `raw/` 配下へ抽出し、ファイル名、SHA-256、ページ別テキストをraw JSONとmanifestへ記録します。案内画面だけを資料本体として扱いません。

第44回は公式indexの全資料がPDFで、市区町村別ページも公開されていません。このような回次では、PDFを取得済みという理由だけで変換済みにせず、`normalized/manifest.json` は全資料を `raw_only` として記録します。市区町村別の未掲載は取得失敗と区別して `manifest.json` の `unavailable_sources` に残します。

各選挙回の `manifest.json` には `.xls`、`.xlsx`、`.pdf` の件数と `normalization_policy` を記録します。`normalized/manifest.json` の `raw_only` は「取得済みだが構造化未検証」を意味し、欠損値や0件として分析に混ぜないでください。
