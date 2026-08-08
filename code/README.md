# code/ ディレクトリについて

ここは作業・復旧・調査用です。  
**一般利用者が回す標準ルートは `docs/PIPELINE.md` と `src/run_pipeline.py` です。**

## 構成

| パス | 役割 |
|------|------|
| `04-smd-gender-muni/build_municipality_all.py` | 互換ラッパー → `src/soumu_election/municipality.py` |
| `03-rebuild-*` / `07-import-*` の再取込スクリプト | 当時の復旧用（通常は pipeline の normalize + warehouse） |
| `08-name-normalize/fix_muni_name_spaces.py` | 空白除去のメンテ用 |
| `_scratch/` | probe / peek / try / diag / ログ（本番外） |

## やること / やらないこと

- 新規の本番処理は `src/soumu_election/` に追加する
- `_scratch/` のスクリプトを README の手順に書かない
- raw を手編集して「修正完了」にしない
