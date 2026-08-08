#!/usr/bin/env python3
"""Prepare Hiroshima OCR review pack under output/ for later manual verification."""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "sangiin22" / "raw"
PREV = ROOT / "code" / "09-sangiin22" / "output"
STAMP = datetime.now().strftime("%Y%m%d_%H%M")
OUT = ROOT / "output" / f"sangiin22-hiroshima-ocr-review_{STAMP}"


README = """# 参院第22回・広島県 市区町村表 OCR確認パック

## 背景
- 総務省公開の広島県市区町村別得票は **画像スキャンPDF**（文字レイヤなし）
- 福岡県はテキストPDFのため機械取込済み
- 広島は Tesseract OCR を試したが、得票数字の精度が実務利用に不足
- そのため市区町村倉庫への自動取込は保留し、本フォルダで事後の人力確認用に切り出し

## 対象ファイル（原典）
| 種別 | ファイル |
|------|----------|
| 選挙区 | `pdf/03-14-district-34_広島県_選挙区_000075925.pdf` |
| 比例・政党別 | `pdf/03-14-pr-party-34_広島県_政党別_000075926.pdf` |
| 比例・候補者別 | `pdf/03-14-pr-cand-34_広島県_候補者別_000075927.pdf` |

出典ページ: https://www.soumu.go.jp/senkyo/senkyo_s/data/sangiin22/sangiin22_7_34.html

## 確認手順（案）
1. `preview/` の PNG でレイアウト・候補者名・市区町村名を目視確認
2. 原典 PDF を開き、選挙区から優先して転記／照合
3. 照合用に少なくとも次を確認:
   - 候補者名（かな／漢字）と党派
   - 各市区町村の得票
   - 県計・市計・町村計との整合
4. 確認結果は `checklist.md` に記入
5. 確定データができたら `normalized/` 相当の JSON/CSV を置き、municipality 再取込対象にする

## OCR試行メモ
- 低解像度・高解像度（300dpi）とも日本語OCRはタイトル程度しか安定せず、得票列は崩れる
- 本番倉庫へ載せない判断（人手確認後に再取込）

## ステータス
- [ ] 選挙区 PDF 目視確認
- [ ] 比例・政党別 目視確認
- [ ] 比例・候補者別 目視確認
- [ ] 転記データ作成
- [ ] warehouse / web 反映
"""


CHECKLIST = """# 人力確認チェックリスト

## 選挙区
- [ ] 候補者5名の氏名・党派が原典と一致
- [ ] 広島市区（中/東/南/西/安佐南/安佐北/安芸/佐伯）得票
- [ ] その他市・町村の得票
- [ ] 県計・市計との検算

## 比例・政党別
- [ ] 政党列の対応確認
- [ ] 主要市区町村サンプル照合（最低10件）

## 比例・候補者別
- [ ] 政党ごとの名簿候補列
- [ ] サンプル照合（各党1ページ以上）

## メモ
（確認日・担当・気づき）


"""


def main() -> int:
    pdf_dir = OUT / "pdf"
    preview_dir = OUT / "preview"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    preview_dir.mkdir(parents=True, exist_ok=True)

    targets = [
        "03-14-district-34_広島県_選挙区_000075925.pdf",
        "03-14-pr-party-34_広島県_政党別_000075926.pdf",
        "03-14-pr-cand-34_広島県_候補者別_000075927.pdf",
    ]
    copied = []
    for name in targets:
        src = RAW / name
        if not src.exists():
            # fuzzy by content id
            stem = name.split("_")[-1]
            hits = list(RAW.glob(f"*{stem}"))
            if hits:
                src = hits[0]
            else:
                print("MISSING", name)
                continue
        dst = pdf_dir / src.name
        shutil.copy2(src, dst)
        copied.append(dst.name)

    if PREV.exists():
        for path in PREV.iterdir():
            if path.is_file() and ("広島" in path.name or "hiroshima" in path.name.lower()):
                shutil.copy2(path, preview_dir / path.name)

    (OUT / "README.md").write_text(README, encoding="utf-8")
    (OUT / "checklist.md").write_text(CHECKLIST, encoding="utf-8")
    print("OUT", OUT)
    print("pdf", copied)
    print("preview", [p.name for p in preview_dir.iterdir()])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
