# -*- coding: utf-8 -*-
"""references 記事 → JSONL → web parquet を一括実行。"""
from __future__ import annotations

import runpy
from pathlib import Path

HERE = Path(__file__).resolve().parent

if __name__ == "__main__":
    runpy.run_path(str(HERE / "build_yomi_pr_meibo_from_articles_v1.0.py"), run_name="__main__")
    runpy.run_path(str(HERE / "export_yomi_pr_meibo_v1.1.py"), run_name="__main__")
