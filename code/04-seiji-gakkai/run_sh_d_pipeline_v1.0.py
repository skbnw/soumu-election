# -*- coding: utf-8 -*-
"""
run_sh_d_pipeline_v1.0.py
- v1.1.1: 表示QAメモ／audit への案内を追加（enrich は pipeline 後に別途）
- v1.1: SH-HD 比例市町村・turnout 粒度拡張を組み込み
- v1.0: 政治学会 SH-D: Bronze → Silver → 選挙区/市区町村 parquet エクスポート → 検証
- MIC facts / municipality_facts は上書きしない

表示QA（絶対得票・地名）:
  code/04-seiji-gakkai/process_display_qa_v1.0.txt
  本 pipeline のあと推奨:
    python code/04-seiji-gakkai/enrich_seiji_gakkai_smd_district_outcome_v1.0.py
    python code/04-seiji-gakkai/audit_municipality_labels_v1.0.py
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CODE = REPO / "references" / "seiji-gakkai" / "code"
HERE = Path(__file__).resolve().parent


def main() -> None:
    sys.path.insert(0, str(CODE))
    print("=== 1/6 Bronze: normalize_sh_d.py ===")
    runpy.run_path(str(CODE / "normalize_sh_d.py"), run_name="__main__")
    print("\n=== 2/6 Silver: normalize_sh_d_to_normalized.py ===")
    runpy.run_path(str(CODE / "normalize_sh_d_to_normalized.py"), run_name="__main__")
    print("\n=== 3/6 Export district parquet (MIC非混在) ===")
    runpy.run_path(str(HERE / "export_seiji_gakkai_smd_district_votes_v1.0.py"), run_name="__main__")
    print("\n=== 4/6 Export municipality parquet (MIC非混在・地名慎重) ===")
    runpy.run_path(str(HERE / "export_seiji_gakkai_smd_municipality_votes_v1.0.py"), run_name="__main__")
    print("\n=== 5/6 Export SH-HD PR municipality parquet ===")
    runpy.run_path(str(HERE / "export_seiji_gakkai_pr_municipality_votes_v1.0.py"), run_name="__main__")
    print("\n=== 6/6 Export turnout (pref/district/muni + PR block) ===")
    runpy.run_path(str(HERE / "export_seiji_gakkai_turnout_v1.0.py"), run_name="__main__")
    print("\n=== verify silver ===")
    runpy.run_path(str(HERE / "verify_sh_d_silver_v1.0.py"), run_name="__main__")
    print("\n=== next (display QA; not auto-run) ===")
    print("python code/04-seiji-gakkai/enrich_seiji_gakkai_smd_district_outcome_v1.0.py")
    print("python code/04-seiji-gakkai/audit_municipality_labels_v1.0.py")
    print("see: code/04-seiji-gakkai/process_display_qa_v1.0.txt")


if __name__ == "__main__":
    main()
