# v1.1.1: pr_party/pr_cand ファイル名のラベル抽出を修正（都道府県コード欠け）
# v1.1.0: 参院（sangiin）市区町村対応（district / pr_party / pr_cand）、election_id・chamber 列
# v1.0.0: 市区町村別得票 parquet 生成（code/04 からパッケージへ移行）
"""Build municipality SMD/PR vote parquets for the warehouse and web explorer."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import duckdb

from soumu_election.download import (
    clean_text,
    find_row,
    find_row_any,
    normalize_person_name,
    parse_pr,
    parse_smd,
    parse_vote,
    workbook_tables,
)

DISTRICT_RE = re.compile(r"第(\d+)区")
PREFECTURE_CODES = {
    name: f"{index:02d}" for index, name in enumerate((
        "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
        "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
        "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県", "岐阜県",
        "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県",
        "奈良県", "和歌山県", "鳥取県", "島根県", "岡山県", "広島県", "山口県",
        "徳島県", "香川県", "愛媛県", "高知県", "福岡県", "佐賀県", "長崎県",
        "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県"), 1)
}
LABEL_SUFFIXES = ("_選挙区", "_合同選挙区", "_政党別", "_候補者別", "_比例代表", "_小選挙区")


def compact_name(value: object) -> str | None:
    text = re.sub(r"[\s\u3000]+", "", str(value or ""))
    return text or None


def source_code_from_name(name: str, prefix: str) -> str:
    match = re.match(rf"({prefix}(?:-\w+)?-\d+)", name)
    if match:
        return match.group(1)
    match = re.match(rf"({prefix}-\d+)", name)
    return match.group(1) if match else prefix


def district_number(district: str | None) -> int | None:
    if not district:
        return None
    match = DISTRICT_RE.search(district)
    return int(match.group(1)) if match else None


def prefecture_from_label(label: str) -> str:
    text = (label or "").strip()
    for suffix in LABEL_SUFFIXES:
        if text.endswith(suffix):
            return text[: -len(suffix)]
    if "_" in text:
        return text.split("_", 1)[0]
    return text


def prefecture_code_of(prefecture: str | None) -> str | None:
    if not prefecture:
        return None
    if prefecture in PREFECTURE_CODES:
        return PREFECTURE_CODES[prefecture]
    # 合区: 先頭都道府県コードを代表値に使う
    for name, code in PREFECTURE_CODES.items():
        if prefecture.startswith(name):
            return code
    return None


def load_manifest_urls(root: Path, chamber: str, kaiji: int) -> dict[str, str]:
    path = root / "data" / f"{chamber}{kaiji}" / "manifest.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    mapping = {}
    for item in data.get("sources", []):
        file_name = Path(str(item.get("file", "")).replace("\\", "/")).name
        if file_name:
            mapping[file_name] = item.get("url") or ""
    return mapping


def election_id_of(chamber: str, kaiji: int) -> str:
    return f"{chamber}-{kaiji}"


def parse_smd_kaiji(root: Path, kaiji: int) -> list[dict]:
    chamber = "shugiin"
    raw_dir = root / "data" / f"{chamber}{kaiji}" / "raw"
    urls = load_manifest_urls(root, chamber, kaiji)
    eid = election_id_of(chamber, kaiji)
    rows: list[dict] = []
    if not raw_dir.exists():
        return rows
    for path in sorted(raw_dir.glob("03-14-smd-*")):
        parts = path.stem.split("_")
        prefecture = parts[1] if len(parts) > 1 else ""
        source = {"label": prefecture, "url": urls.get(path.name, ""), "category": "smd"}
        try:
            records = parse_smd(path, source, kaiji)
        except Exception as exc:
            print(f"FAIL SMD {kaiji} {path.name}: {exc}", flush=True)
            continue
        code = source_code_from_name(path.name, "03-14-smd")
        for item in records:
            if item.get("row_type") != "reporting_unit":
                continue
            rows.append({
                "election_id": eid,
                "chamber": chamber,
                "election_kaiji": kaiji,
                "category": "小選挙区",
                "contest": "smd",
                "prefecture": item["prefecture"],
                "prefecture_code": PREFECTURE_CODES.get(item["prefecture"]),
                "district_number": district_number(item.get("district")),
                "municipality": compact_name(item.get("reporting_unit")),
                "subject": compact_name(item.get("candidate")),
                "candidate": compact_name(item.get("candidate")),
                "party": compact_name(item.get("party")),
                "metric": "candidate_votes",
                "value": item.get("votes"),
                "unit": "votes",
                "grain": "municipality",
                "source_code": code,
                "source_file": item.get("source_file"),
            })
    return rows


def parse_pr_kaiji(root: Path, kaiji: int) -> list[dict]:
    chamber = "shugiin"
    raw_dir = root / "data" / f"{chamber}{kaiji}" / "raw"
    urls = load_manifest_urls(root, chamber, kaiji)
    eid = election_id_of(chamber, kaiji)
    rows: list[dict] = []
    if not raw_dir.exists():
        return rows
    for path in sorted(raw_dir.glob("03-14-pr-*")):
        parts = path.stem.split("_")
        label = parts[1] if len(parts) > 1 else ""
        source = {"label": label, "url": urls.get(path.name, ""), "category": "pr"}
        try:
            records = parse_pr(path, source, kaiji)
        except Exception as exc:
            print(f"FAIL PR {kaiji} {path.name}: {exc}", flush=True)
            continue
        code = source_code_from_name(path.name, "03-14-pr")
        for item in records:
            if item.get("row_type") != "reporting_unit":
                continue
            area = item.get("source_area") or ""
            prefecture = area if area in PREFECTURE_CODES else None
            if prefecture is None:
                block = str(item.get("block") or "")
                for pref in PREFECTURE_CODES:
                    if pref.replace("県", "").replace("府", "").replace("都", "") in block.replace("選挙区", ""):
                        if block.startswith(pref[:2]) or pref.startswith(block.replace("選挙区", "")[:2]):
                            prefecture = pref
                            break
                if label in PREFECTURE_CODES:
                    prefecture = label
                elif area in PREFECTURE_CODES:
                    prefecture = area
            if prefecture is None and label in PREFECTURE_CODES:
                prefecture = label
            if prefecture is None:
                prefecture = area if area else None
            rows.append({
                "election_id": eid,
                "chamber": chamber,
                "election_kaiji": kaiji,
                "category": "比例代表",
                "contest": "pr",
                "prefecture": prefecture,
                "prefecture_code": PREFECTURE_CODES.get(prefecture) if prefecture else None,
                "district_number": None,
                "municipality": compact_name(item.get("reporting_unit")),
                "pr_block": item.get("block"),
                "subject": compact_name(item.get("party")),
                "candidate": None,
                "party": compact_name(item.get("party")),
                "metric": "party_votes",
                "value": item.get("votes"),
                "unit": "votes",
                "grain": "municipality",
                "source_code": code,
                "source_file": item.get("source_file"),
            })
    return rows


def parse_sangiin_muni_district(path: Path, source: dict[str, str], kaiji: int) -> list[dict]:
    """参院 選挙区・候補者別市区町村得票（衆院 SMD と同型＋政党等名）。"""
    prefecture = prefecture_from_label(source.get("label") or "")
    adjusted = {**source, "label": prefecture}
    records = parse_smd(path, adjusted, kaiji)
    eid = election_id_of("sangiin", kaiji)
    code = source_code_from_name(path.name, "03-14-district")
    rows: list[dict] = []
    for item in records:
        if item.get("row_type") != "reporting_unit":
            continue
        rows.append({
            "election_id": eid,
            "chamber": "sangiin",
            "election_kaiji": kaiji,
            "category": "選挙区",
            "contest": "district",
            "prefecture": prefecture,
            "prefecture_code": prefecture_code_of(prefecture),
            "district_number": None,
            "municipality": compact_name(item.get("reporting_unit")),
            "subject": compact_name(item.get("candidate")),
            "candidate": compact_name(item.get("candidate")),
            "party": compact_name(item.get("party")),
            "metric": "candidate_votes",
            "value": item.get("votes"),
            "unit": "votes",
            "grain": "municipality",
            "source_code": code,
            "source_file": item.get("source_file") or path.name,
        })
    return rows


def parse_sangiin_muni_pr_party(path: Path, source: dict[str, str], kaiji: int) -> list[dict]:
    """参院 比例・政党別市区町村得票（党ごとに得票総数/政党/名簿の3列）。"""
    prefecture = prefecture_from_label(source.get("label") or "")
    eid = election_id_of("sangiin", kaiji)
    code = source_code_from_name(path.name, "03-14-pr_party")
    if "pr-party" in path.name:
        code = source_code_from_name(path.name, "03-14-pr-party")
    rows: list[dict] = []
    for sheet_name, table in workbook_tables(path):
        try:
            open_row = find_row(table, "開票区名")
        except ValueError:
            continue
        party_cols: list[tuple[int, str]] = []
        for index in range(open_row - 1, -1, -1):
            found: list[tuple[int, str]] = []
            for column, cell in enumerate(table[index]):
                if column == 0:
                    continue
                text = clean_text(cell)
                if not text or "単位" in text or "届出" in text or text.isdigit():
                    continue
                if text in {"政党等名", "得票総数", "政党等の", "名簿登載者の"}:
                    continue
                found.append((column, text))
            if len(found) >= 2:
                party_cols = found
                break
        if not party_cols:
            continue
        data_start = open_row + 1
        while data_start < len(table):
            label = clean_text(table[data_start][0] if table[data_start] else None)
            sample = parse_vote(table[data_start][party_cols[0][0]] if len(table[data_start]) > party_cols[0][0] else None)
            if label and sample is not None:
                break
            data_start += 1
        for excel_row, row in enumerate(table[data_start:], start=data_start + 1):
            municipality = clean_text(row[0]) if row else None
            if not municipality:
                continue
            if municipality.endswith("計") or municipality in {"合計", "総計"}:
                continue
            for start_col, party in party_cols:
                # 3列組: 得票総数 / 政党等の得票総数 / 名簿登載者の得票総数 → 政党列を採用
                vote_col = start_col + 1
                vote = parse_vote(row[vote_col] if vote_col < len(row) else None)
                if vote is None:
                    vote = parse_vote(row[start_col] if start_col < len(row) else None)
                if vote is None:
                    continue
                rows.append({
                    "election_id": eid,
                    "chamber": "sangiin",
                    "election_kaiji": kaiji,
                    "category": "比例代表",
                    "contest": "pr",
                    "prefecture": prefecture,
                    "prefecture_code": prefecture_code_of(prefecture),
                    "district_number": None,
                    "municipality": compact_name(municipality),
                    "pr_block": None,
                    "subject": compact_name(party),
                    "candidate": None,
                    "party": compact_name(party),
                    "metric": "party_votes",
                    "value": vote,
                    "unit": "votes",
                    "grain": "municipality",
                    "source_code": code,
                    "source_file": path.name,
                    "source_sheet": sheet_name,
                    "source_row": excel_row,
                })
    return rows


def parse_sangiin_muni_pr_cand(path: Path, source: dict[str, str], kaiji: int) -> list[dict]:
    """参院 比例・名簿登載者別市区町村得票（シート＝政党）。"""
    prefecture = prefecture_from_label(source.get("label") or "")
    eid = election_id_of("sangiin", kaiji)
    code = source_code_from_name(path.name, "03-14-pr_cand")
    if "pr-cand" in path.name:
        code = source_code_from_name(path.name, "03-14-pr-cand")
    rows: list[dict] = []
    for sheet_name, table in workbook_tables(path):
        party = clean_text(sheet_name) or ""
        for index, row in enumerate(table[:12]):
            if clean_text(row[0] if row else None) == "政党等の名称" and index + 1 < len(table):
                named = clean_text(table[index + 1][0] if table[index + 1] else None)
                if named:
                    party = named
                break
        try:
            header = find_row_any(table, ("開票区名/名簿登載者名", "名簿登載者名", "開票区名"))
        except ValueError:
            continue
        candidates: list[tuple[int, str]] = []
        for column in range(1, len(table[header])):
            name = clean_text(table[header][column])
            if not name:
                continue
            candidates.append((column, name))
        if not candidates:
            continue
        for excel_row, row in enumerate(table[header + 1 :], start=header + 2):
            municipality = clean_text(row[0]) if row else None
            if not municipality:
                continue
            if municipality.endswith("計") or municipality in {"合計", "総計"}:
                continue
            for column, candidate_raw in candidates:
                vote = parse_vote(row[column] if column < len(row) else None)
                if vote is None:
                    continue
                cand = normalize_person_name(candidate_raw)
                rows.append({
                    "election_id": eid,
                    "chamber": "sangiin",
                    "election_kaiji": kaiji,
                    "category": "比例代表",
                    "contest": "pr",
                    "prefecture": prefecture,
                    "prefecture_code": prefecture_code_of(prefecture),
                    "district_number": None,
                    "municipality": compact_name(municipality),
                    "pr_block": None,
                    "subject": compact_name(cand),
                    "candidate": compact_name(cand),
                    "party": compact_name(party),
                    "metric": "candidate_votes",
                    "value": vote,
                    "unit": "votes",
                    "grain": "municipality",
                    "source_code": code,
                    "source_file": path.name,
                    "source_sheet": sheet_name,
                    "source_row": excel_row,
                })
    return rows


def label_from_muni_filename(name: str) -> str:
    """03-14-* ファイル名から都道府県_種別ラベルを取り出す。"""
    stem = Path(name).stem
    match = re.match(
        r"03-14-(?:district|pr_party|pr-party|pr_cand|pr-cand|smd|pr)-\d+_(.+)$",
        stem,
    )
    if not match:
        parts = stem.split("_")
        return "_".join(parts[1:-1]) if len(parts) > 2 else (parts[1] if len(parts) > 1 else stem)
    rest = match.group(1)
    head, tail = rest.rsplit("_", 1) if "_" in rest else (rest, "")
    if tail.isdigit():
        return head
    return rest


def parse_sangiin_kaiji(root: Path, kaiji: int) -> list[dict]:
    chamber = "sangiin"
    raw_dir = root / "data" / f"{chamber}{kaiji}" / "raw"
    urls = load_manifest_urls(root, chamber, kaiji)
    rows: list[dict] = []
    if not raw_dir.exists():
        return rows

    for path in sorted(raw_dir.glob("03-14-district-*")):
        label = label_from_muni_filename(path.name)
        source = {"label": label, "url": urls.get(path.name, ""), "category": "district"}
        try:
            rows.extend(parse_sangiin_muni_district(path, source, kaiji))
        except Exception as exc:
            print(f"FAIL sangiin district {kaiji} {path.name}: {exc}", flush=True)

    for path in sorted([*raw_dir.glob("03-14-pr_party-*"), *raw_dir.glob("03-14-pr-party-*")]):
        label = label_from_muni_filename(path.name)
        source = {"label": label, "url": urls.get(path.name, ""), "category": "pr_party"}
        try:
            rows.extend(parse_sangiin_muni_pr_party(path, source, kaiji))
        except Exception as exc:
            print(f"FAIL sangiin pr_party {kaiji} {path.name}: {exc}", flush=True)

    for path in sorted([*raw_dir.glob("03-14-pr_cand-*"), *raw_dir.glob("03-14-pr-cand-*")]):
        label = label_from_muni_filename(path.name)
        source = {"label": label, "url": urls.get(path.name, ""), "category": "pr_cand"}
        try:
            rows.extend(parse_sangiin_muni_pr_cand(path, source, kaiji))
        except Exception as exc:
            print(f"FAIL sangiin pr_cand {kaiji} {path.name}: {exc}", flush=True)

    return rows


def write_parquet(rows: list[dict], path: Path) -> None:
    out_dir = path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    ndjson = path.with_suffix(".ndjson")
    with ndjson.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    con = duckdb.connect()
    src = ndjson.as_posix().replace("'", "''")
    dst = path.as_posix().replace("'", "''")
    con.execute(f"""
        COPY (
          SELECT * FROM read_json_auto('{src}', format='newline_delimited', union_by_name=true)
        ) TO '{dst}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    con.close()
    ndjson.unlink(missing_ok=True)


def build_municipality_facts(
    root: Path,
    kaiji_list: list[int] | None = None,
    *,
    sangiin_kaiji: list[int] | None = None,
    write_legacy: bool = True,
) -> dict:
    """Generate municipality_facts.parquet under warehouse and web/data."""
    kaiji_list = kaiji_list if kaiji_list is not None else list(range(45, 52))
    sangiin_kaiji = sangiin_kaiji or []
    all_rows: list[dict] = []
    summary = []
    for kaiji in kaiji_list:
        print(f"parsing municipality shugiin {kaiji} ...", flush=True)
        smd_rows = parse_smd_kaiji(root, kaiji)
        pr_rows = parse_pr_kaiji(root, kaiji)
        rows = smd_rows + pr_rows
        summary.append({
            "chamber": "shugiin",
            "kaiji": kaiji,
            "smd": len(smd_rows),
            "pr": len(pr_rows),
            "total": len(rows),
        })
        print(summary[-1], flush=True)
        all_rows.extend(rows)

    for kaiji in sangiin_kaiji:
        print(f"parsing municipality sangiin {kaiji} ...", flush=True)
        rows = parse_sangiin_kaiji(root, kaiji)
        summary.append({
            "chamber": "sangiin",
            "kaiji": kaiji,
            "total": len(rows),
        })
        print(summary[-1], flush=True)
        all_rows.extend(rows)

    warehouse = root / "data" / "warehouse" / "parquet" / "municipality_facts.parquet"
    web = root / "web" / "data" / "municipality_facts.parquet"
    write_parquet(all_rows, warehouse)
    web.parent.mkdir(parents=True, exist_ok=True)
    web.write_bytes(warehouse.read_bytes())

    if write_legacy:
        smd_only = [r for r in all_rows if r["category"] == "小選挙区"]
        legacy = root / "data" / "warehouse" / "parquet" / "smd_municipality_votes.parquet"
        legacy_web = root / "web" / "data" / "smd_municipality_votes.parquet"
        write_parquet(smd_only, legacy)
        legacy_web.write_bytes(legacy.read_bytes())

    result = {
        "total": len(all_rows),
        "by_kaiji": summary,
        "bytes": warehouse.stat().st_size,
        "path": str(warehouse),
    }
    print(result, flush=True)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build municipality_facts.parquet from 03-14 workbooks")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--kaiji", type=int, nargs="*", default=list(range(45, 52)))
    parser.add_argument("--sangiin-kaiji", type=int, nargs="*", default=[], help="参院回次（例: 26）")
    parser.add_argument("--no-legacy", action="store_true", help="smd_municipality_votes.parquet を書かない")
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    build_municipality_facts(
        root,
        args.kaiji,
        sangiin_kaiji=args.sangiin_kaiji,
        write_legacy=not args.no_legacy,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
