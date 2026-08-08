# v1.0.0: 公開向け一本道 CLI（download → normalize → warehouse → municipality）
"""Run the standard shugiin data pipeline end-to-end."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


STEP_ORDER = ("download", "normalize", "warehouse", "municipality")
DEFAULT_KAIJI = list(range(44, 52))
MUNI_KAIJI_DEFAULT = list(range(45, 52))


def _run_download(root: Path, kaiji: int, *, force: bool) -> int:
    from soumu_election.download import main as download_main

    argv = ["--kaiji", str(kaiji), "--output", str(root / "data" / f"shugiin{kaiji}")]
    if force:
        argv.append("--force")
    old = sys.argv
    try:
        sys.argv = ["soumu_election.download", *argv]
        return int(download_main() or 0)
    finally:
        sys.argv = old


def _run_normalize(root: Path, kaiji: int) -> int:
    from soumu_election.normalize import main as normalize_main

    raw_json = root / "data" / f"shugiin{kaiji}" / "raw_json"
    out = root / "data" / f"shugiin{kaiji}" / "normalized"
    if not raw_json.exists():
        raise FileNotFoundError(f"missing raw_json: {raw_json}")
    old = sys.argv
    try:
        sys.argv = [
            "soumu_election.normalize",
            "--input", str(raw_json),
            "--output", str(out),
        ]
        return int(normalize_main() or 0)
    finally:
        sys.argv = old


def _run_warehouse(root: Path, kaiji_list: list[int]) -> int:
    from soumu_election.warehouse import main as warehouse_main

    old = sys.argv
    try:
        sys.argv = [
            "soumu_election.warehouse",
            "--project-root", str(root),
            "--kaiji", *[str(k) for k in kaiji_list],
        ]
        return int(warehouse_main() or 0)
    finally:
        sys.argv = old


def _run_municipality(root: Path, kaiji_list: list[int]) -> int:
    from soumu_election.municipality import main as municipality_main

    muni_kaiji = [k for k in kaiji_list if k >= 45] or MUNI_KAIJI_DEFAULT
    return int(municipality_main([
        "--project-root", str(root),
        "--kaiji", *[str(k) for k in muni_kaiji],
    ]) or 0)


def parse_steps(raw: str) -> list[str]:
    steps = [part.strip() for part in raw.split(",") if part.strip()]
    unknown = [s for s in steps if s not in STEP_ORDER]
    if unknown:
        raise SystemExit(f"unknown steps: {unknown}; choose from {list(STEP_ORDER)}")
    return steps


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "衆院選データの標準パイプライン。"
            "総務省サイト取得 → 正規化 → warehouse → 市区町村parquet。"
        )
    )
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--kaiji", type=int, nargs="*", default=DEFAULT_KAIJI,
        help="対象回次（既定: 44〜51）",
    )
    parser.add_argument(
        "--steps", default="download,normalize,warehouse,municipality",
        help=f"実行ステップ（カンマ区切り）。候補: {','.join(STEP_ORDER)}",
    )
    parser.add_argument(
        "--force-download", action="store_true",
        help="download 時に既存原本を再取得",
    )
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    steps = parse_steps(args.steps)
    kaiji_list = args.kaiji

    print({
        "project_root": str(root),
        "kaiji": kaiji_list,
        "steps": steps,
    }, flush=True)

    # warehouse は検証failでもparquetを書くことがあるため、後続へ進み最終コードで返す
    final_code = 0
    for step in steps:
        if step == "download":
            for kaiji in kaiji_list:
                print(f"== download shugiin{kaiji} ==", flush=True)
                code = _run_download(root, kaiji, force=args.force_download)
                if code:
                    return code
        elif step == "normalize":
            for kaiji in kaiji_list:
                print(f"== normalize shugiin{kaiji} ==", flush=True)
                code = _run_normalize(root, kaiji)
                if code:
                    return code
        elif step == "warehouse":
            print("== warehouse ==", flush=True)
            code = _run_warehouse(root, kaiji_list)
            if code:
                final_code = code
                print("warehouse returned non-zero; continuing remaining steps", flush=True)
        elif step == "municipality":
            print("== municipality ==", flush=True)
            code = _run_municipality(root, kaiji_list)
            if code:
                return code
    return final_code


if __name__ == "__main__":
    raise SystemExit(main())
