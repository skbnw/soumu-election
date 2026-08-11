# v1.3.2: 関西大選挙区CSVを都道府県集計し、参院県区facts（21–23）を補充
# v1.3.1: 関西大穴埋めで参22のMIC未接続9県（青森・宮城・東京・神奈川・愛知・広島・香川・高知・鹿児島）に拡大
# v1.3.0: 関西大・参院選DB（二次ソース）で参21全面・参22広島など穴埋め
# v1.2.0: 参院市区町村PDF（テキスト抽出可能な福岡など）を取込
# v1.1.2: 市区町村名の選挙区接尾辞を統一（全角/半角括弧・数字）
# v1.1.1: pr_party/pr_cand ファイル名のラベル抽出を修正（都道府県コード欠け）
# v1.1.0: 参院（sangiin）市区町村対応（district / pr_party / pr_cand）、election_id・chamber 列
# v1.0.0: 市区町村別得票 parquet 生成（code/04 からパッケージへ移行）
"""Build municipality SMD/PR vote parquets for the warehouse and web explorer."""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any, Iterable

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

# 関西大・比較政治研究DB（参院選DB / 名取研究室）二次ソース
KANSAI_REF_DIR = Path("references") / "sangiin-kansai-u.ac.jp"
KANSAI_SOURCE_PREFIX = "kansai"
KANSAI_KIND_FILES = {
    "district": ("01-選挙区", "01-senkyoku-{kaiji}.csv"),
    "pr_party": ("03-比例区(政党別)", "03-hirei-seitoubetu-{kaiji}.csv"),
    "pr_cand": ("04-比例区(個人別)", "04-hirei-kojinbetu-{kaiji}.csv"),
}
KANSAI_DB_URL = "http://db.cps.kutc.kansai-u.ac.jp/main/index1.php"
KANSAI_STATUS_MAP = {"新": "new", "現": "incumbent", "前": "incumbent", "元": "former"}
# 手元の関西大選挙区CSVで県区（都道府県集計）を補充できる回
KANSAI_DISTRICT_PREF_KAIJI = (19, 20, 21, 22, 23)

DISTRICT_RE = re.compile(r"第(\d+)区")
# 例: 札幌市西区（１区） / さいたま市見沼区(1区) / 南九州市(２区） / 札幌市西区第（４区）
DISTRICT_SUFFIX_RE = re.compile(
    r"(?:第)?[（(]\s*([0-9０-９]+)\s*区\s*[）)]\s*$"
)
ZENKAKU_DIGIT_TRANS = str.maketrans("０１２３４５６７８９", "0123456789")
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


def normalize_municipality_name(value: object) -> str | None:
    """市区町村ラベルを統一する。

    選挙区接尾辞は全角括弧＋半角数字に揃える（例: 札幌市西区（1区））。
    """
    text = compact_name(value)
    if not text:
        return None
    match = DISTRICT_SUFFIX_RE.search(text)
    if not match:
        return text
    digits = match.group(1).translate(ZENKAKU_DIGIT_TRANS)
    base = text[: match.start()]
    # 「西区第」のように余分な「第」が残る場合を除去
    if base.endswith("第"):
        base = base[:-1]
    return f"{base}（{digits}区）"


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
                "municipality": normalize_municipality_name(item.get("reporting_unit")),
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
                "municipality": normalize_municipality_name(item.get("reporting_unit")),
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


def extract_pdf_tables(path: Path) -> list[list[list[Any]]]:
    """Extract tables from text-based PDFs via pdfplumber."""
    import pdfplumber

    tables: list[list[list[Any]]] = []
    with pdfplumber.open(path) as pdf:
        if not any(len(page.chars) > 20 for page in pdf.pages[: min(2, len(pdf.pages))]):
            raise ValueError(f"画像スキャンPDFのためテキスト表を抽出できません: {path.name}")
        for page in pdf.pages:
            for table in page.extract_tables() or []:
                cleaned: list[list[Any]] = []
                for row in table:
                    cleaned.append([
                        (cell.replace("\n", "") if isinstance(cell, str) else cell)
                        for cell in row
                    ])
                # skip tiny junk tables
                if len(cleaned) >= 3 and max(len(r) for r in cleaned) >= 3:
                    tables.append(cleaned)
    if not tables:
        raise ValueError(f"PDF表が見つかりません: {path.name}")
    return tables


def parse_sangiin_muni_district_pdf(path: Path, source: dict[str, str], kaiji: int) -> list[dict]:
    """参院選挙区・市区町村得票（テキストPDF。福岡22など）。"""
    prefecture = prefecture_from_label(source.get("label") or "")
    eid = election_id_of("sangiin", kaiji)
    code = source_code_from_name(path.name, "03-14-district")
    rows: list[dict] = []
    for table in extract_pdf_tables(path):
        party_row_i = None
        cand_row_i = None
        for i, row in enumerate(table[:6]):
            texts = [clean_text(c) for c in row]
            if any(t and ("党" in t or t == "無所属") for t in texts[1:]):
                party_row_i = i
            if party_row_i is not None and i > party_row_i:
                if sum(1 for t in texts[1:] if t and not t.isdigit() and "計" not in t) >= 2:
                    cand_row_i = i
                    break
        if party_row_i is None or cand_row_i is None:
            if len(table) >= 3:
                party_row_i, cand_row_i = 1, 2
            else:
                continue
        parties = table[party_row_i]
        cands = table[cand_row_i]
        cols: list[tuple[int, str, str | None]] = []
        for col in range(1, max(len(parties), len(cands))):
            cand = clean_text(cands[col] if col < len(cands) else None)
            party = clean_text(parties[col] if col < len(parties) else None)
            if not cand or cand.isdigit() or "小計" in cand or cand == "計":
                continue
            cols.append((col, cand, party))
        for row in table[cand_row_i + 1 :]:
            muni = clean_text(row[0] if row else None)
            if not muni or muni.endswith("計") or muni in {"合計", "総計"} or "＊" in muni:
                continue
            for col, cand_raw, party in cols:
                vote = parse_vote(row[col] if col < len(row) else None)
                if vote is None:
                    continue
                cand = normalize_person_name(cand_raw)
                rows.append({
                    "election_id": eid,
                    "chamber": "sangiin",
                    "election_kaiji": kaiji,
                    "category": "選挙区",
                    "contest": "district",
                    "prefecture": prefecture,
                    "prefecture_code": prefecture_code_of(prefecture),
                    "district_number": None,
                    "municipality": normalize_municipality_name(muni),
                    "subject": compact_name(cand),
                    "candidate": compact_name(cand),
                    "party": compact_name(party),
                    "metric": "candidate_votes",
                    "value": vote,
                    "unit": "votes",
                    "grain": "municipality",
                    "source_code": code,
                    "source_file": path.name,
                })
    return rows


def parse_sangiin_muni_pr_party_pdf(path: Path, source: dict[str, str], kaiji: int) -> list[dict]:
    """参院比例・政党別市区町村得票（テキストPDF）。"""
    prefecture = prefecture_from_label(source.get("label") or "")
    eid = election_id_of("sangiin", kaiji)
    code = source_code_from_name(path.name, "03-14-pr_party")
    if "pr-party" in path.name:
        code = source_code_from_name(path.name, "03-14-pr-party")
    rows: list[dict] = []
    for table in extract_pdf_tables(path):
        party_row_i = None
        for i, row in enumerate(table[:5]):
            texts = [clean_text(c) for c in row[1:]]
            if sum(1 for t in texts if t and ("党" in t or "改革" in t or "創新" in t or t == "無所属")) >= 2:
                party_row_i = i
                break
        if party_row_i is None:
            party_row_i = 1
        parties = table[party_row_i]
        cols: list[tuple[int, str]] = []
        for col in range(1, len(parties)):
            party = clean_text(parties[col])
            if not party or party.isdigit() or "小計" in party:
                continue
            cols.append((col, party))
        for row in table[party_row_i + 1 :]:
            muni = clean_text(row[0] if row else None)
            if not muni or muni.endswith("計") or muni in {"合計", "総計"} or "＊" in muni:
                continue
            for col, party in cols:
                vote = parse_vote(row[col] if col < len(row) else None)
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
                    "municipality": normalize_municipality_name(muni),
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
                })
    return rows


def parse_sangiin_muni_pr_cand_pdf(path: Path, source: dict[str, str], kaiji: int) -> list[dict]:
    """参院比例・名簿候補別市区町村得票（テキストPDF）。"""
    prefecture = prefecture_from_label(source.get("label") or "")
    eid = election_id_of("sangiin", kaiji)
    code = source_code_from_name(path.name, "03-14-pr_cand")
    if "pr-cand" in path.name:
        code = source_code_from_name(path.name, "03-14-pr-cand")
    rows: list[dict] = []
    for table in extract_pdf_tables(path):
        if len(table) < 3:
            continue
        header = table[0]
        names = table[1]
        party = None
        for cell in header[1:4]:
            text = clean_text(cell)
            if not text:
                continue
            match = re.match(r"(.+?)(?:合計|政党|候補者)", text)
            if match:
                party = match.group(1)
                break
            if "党" in text:
                party = re.sub(r"(合計|政党|候補者).*$", "", text)
                break
        use_cols: list[tuple[int, str]] = []
        for col in range(1, max(len(header), len(names))):
            h = clean_text(header[col] if col < len(header) else None) or ""
            n = clean_text(names[col] if col < len(names) else None) or ""
            if any(k in h for k in ("合計得票", "政党得票", "候補者得票")):
                continue
            if re.fullmatch(r"\d{1,2}", h) and n:
                use_cols.append((col, n))
        if not use_cols:
            continue
        for row in table[2:]:
            muni = clean_text(row[0] if row else None)
            if not muni or muni.endswith("計") or "＊" in muni:
                continue
            for col, cand_raw in use_cols:
                vote = parse_vote(row[col] if col < len(row) else None)
                if vote is None:
                    continue
                cand = normalize_person_name(cand_raw)
                rows.append({
                    "election_id": eid,
                    "chamber": "sangiin",
                    "election_kaiji": kaiji,
                    "category": "比例代表",
                    "contest": "pr",
                    "prefecture": prefecture,
                    "prefecture_code": prefecture_code_of(prefecture),
                    "district_number": None,
                    "municipality": normalize_municipality_name(muni),
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
                })
    return rows


def parse_sangiin_muni_district(path: Path, source: dict[str, str], kaiji: int) -> list[dict]:
    """参院 選挙区・候補者別市区町村得票（衆院 SMD と同型＋政党等名）。"""
    if path.suffix.lower() == ".pdf":
        return parse_sangiin_muni_district_pdf(path, source, kaiji)
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
            "municipality": normalize_municipality_name(item.get("reporting_unit")),
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
    if path.suffix.lower() == ".pdf":
        return parse_sangiin_muni_pr_party_pdf(path, source, kaiji)
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
                    "municipality": normalize_municipality_name(municipality),
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
    if path.suffix.lower() == ".pdf":
        return parse_sangiin_muni_pr_cand_pdf(path, source, kaiji)
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
                    "municipality": normalize_municipality_name(municipality),
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


def kansai_ref_root(root: Path) -> Path:
    return root / KANSAI_REF_DIR


def kansai_csv_path(root: Path, kind: str, kaiji: int) -> Path | None:
    spec = KANSAI_KIND_FILES.get(kind)
    if not spec:
        return None
    subdir, pattern = spec
    path = kansai_ref_root(root) / subdir / pattern.format(kaiji=kaiji)
    return path if path.exists() else None


def _read_kansai_csv(path: Path) -> list[dict[str, str]]:
    raw = path.read_bytes()
    text = None
    for enc in ("cp932", "utf-8-sig", "utf-8"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise ValueError(f"文字コードを判定できません: {path}")
    lines = text.splitlines()
    if not lines:
        return []
    # Dataverse系DLの先頭メタ行（city/none/normalized/...）をスキップ
    start = 1 if lines[0].startswith("city/") or "normalized/" in lines[0] else 0
    return list(csv.DictReader(lines[start:]))


def parse_kansai_sangiin_kind(
    root: Path,
    kaiji: int,
    kind: str,
    *,
    prefectures: Iterable[str] | None = None,
) -> list[dict]:
    """関西大・参院選DB CSV を municipality_facts 行へ変換する（二次ソース）。"""
    path = kansai_csv_path(root, kind, kaiji)
    if path is None:
        return []
    pref_filter = {p for p in (prefectures or []) if p} or None
    eid = election_id_of("sangiin", kaiji)
    source_code = f"{KANSAI_SOURCE_PREFIX}-{kind}-{kaiji:02d}"
    rows: list[dict] = []
    for item in _read_kansai_csv(path):
        prefecture = clean_text(item.get("都道府県名"))
        if not prefecture:
            continue
        if pref_filter is not None and prefecture not in pref_filter:
            continue
        muni = normalize_municipality_name(item.get("市区町村名"))
        if not muni:
            continue
        vote = parse_vote(item.get("市区町村別得票数"))
        if vote is None:
            continue
        party = compact_name(item.get("党派・会派等"))
        name_raw = clean_text(item.get("名前"))
        cand = compact_name(normalize_person_name(name_raw)) if name_raw else None

        if kind == "pr_party":
            if not party:
                continue
            category, contest, metric = "比例代表", "pr", "party_votes"
            subject, candidate = party, None
        elif kind == "pr_cand":
            if not cand:
                continue
            category, contest, metric = "比例代表", "pr", "candidate_votes"
            subject, candidate = cand, cand
        else:  # district
            if not cand:
                continue
            category, contest, metric = "選挙区", "district", "candidate_votes"
            subject, candidate = cand, cand

        rows.append({
            "election_id": eid,
            "chamber": "sangiin",
            "election_kaiji": kaiji,
            "category": category,
            "contest": contest,
            "prefecture": prefecture,
            "prefecture_code": prefecture_code_of(prefecture),
            "district_number": None,
            "municipality": muni,
            "pr_block": None,
            "subject": subject,
            "candidate": candidate,
            "party": party,
            "metric": metric,
            "value": vote,
            "unit": "votes",
            "grain": "municipality",
            "source_code": source_code,
            "source_file": path.name,
        })
    return rows


def parse_kansai_sangiin_fill(
    root: Path,
    kaiji: int,
    *,
    prefectures: Iterable[str] | None = None,
    kinds: Iterable[str] = ("district", "pr_party", "pr_cand"),
) -> list[dict]:
    """指定回の関西大CSVを種類ごとに取り込む。"""
    if not kansai_ref_root(root).exists():
        return []
    rows: list[dict] = []
    for kind in kinds:
        part = parse_kansai_sangiin_kind(root, kaiji, kind, prefectures=prefectures)
        print(
            f"kansai fill sangiin {kaiji} {kind}: {len(part)} rows"
            + (f" prefs={sorted(set(prefectures))}" if prefectures else ""),
            flush=True,
        )
        rows.extend(part)
    return rows


def default_kansai_fill_specs() -> list[dict[str, Any]]:
    """当面の穴埋め対象: 参19全面 + 参20全面 + 参21全面 + 参22のMIC未接続都道府県。"""
    return [
        {"kaiji": 19, "prefectures": None},
        {"kaiji": 20, "prefectures": None},
        {"kaiji": 21, "prefectures": None},
        {
            "kaiji": 22,
            "prefectures": [
                "青森県",
                "宮城県",
                "東京都",
                "神奈川県",
                "愛知県",
                "広島県",
                "香川県",
                "高知県",
                "鹿児島県",
            ],
        },
    ]


def parse_sangiin_kaiji(
    root: Path,
    kaiji: int,
    *,
    kansai_fill: bool = True,
    kansai_prefs: Iterable[str] | None = None,
) -> list[dict]:
    chamber = "sangiin"
    raw_dir = root / "data" / f"{chamber}{kaiji}" / "raw"
    urls = load_manifest_urls(root, chamber, kaiji)
    rows: list[dict] = []
    if raw_dir.exists():
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

    if kansai_fill:
        if kansai_prefs is not None:
            prefs: list[str] | None = list(kansai_prefs)
        else:
            specs = {s["kaiji"]: s.get("prefectures") for s in default_kansai_fill_specs()}
            if kaiji not in specs:
                return rows
            prefs = specs[kaiji]
        rows.extend(parse_kansai_sangiin_fill(root, kaiji, prefectures=prefs))

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


def merge_kansai_into_municipality_facts(
    root: Path,
    specs: list[dict[str, Any]] | None = None,
) -> dict:
    """既存 municipality_facts に関西大穴埋め行をマージして書き戻す。"""
    specs = specs or default_kansai_fill_specs()
    warehouse = root / "data" / "warehouse" / "parquet" / "municipality_facts.parquet"
    web = root / "web" / "data" / "municipality_facts.parquet"
    if not warehouse.exists() and not web.exists():
        raise FileNotFoundError("municipality_facts.parquet が見つかりません")
    src = warehouse if warehouse.exists() else web

    new_rows: list[dict] = []
    for spec in specs:
        kaiji = int(spec["kaiji"])
        prefs = spec.get("prefectures")
        new_rows.extend(parse_kansai_sangiin_fill(root, kaiji, prefectures=prefs))

    drop_codes = sorted({r["source_code"] for r in new_rows})
    tmp_new = warehouse.parent / "_kansai_new.parquet"
    write_parquet(new_rows, tmp_new)

    con = duckdb.connect()
    code_list = ", ".join("'" + c.replace("'", "''") + "'" for c in drop_codes) or "''"
    con.execute(
        f"""
        CREATE OR REPLACE TABLE merged AS
        SELECT * FROM read_parquet(?)
        WHERE source_code IS NULL OR cast(source_code AS VARCHAR) NOT IN ({code_list})
        """,
        [str(src)],
    )
    kept = con.execute("SELECT count(*) FROM merged").fetchone()[0]
    con.execute("INSERT INTO merged BY NAME SELECT * FROM read_parquet(?)", [str(tmp_new)])
    total = con.execute("SELECT count(*) FROM merged").fetchone()[0]
    warehouse.parent.mkdir(parents=True, exist_ok=True)
    con.execute(
        "COPY merged TO ? (FORMAT PARQUET, COMPRESSION ZSTD)",
        [str(warehouse)],
    )
    con.close()
    tmp_new.unlink(missing_ok=True)

    web.parent.mkdir(parents=True, exist_ok=True)
    web.write_bytes(warehouse.read_bytes())
    result = {
        "added": len(new_rows),
        "kept": int(kept),
        "total": int(total),
        "bytes": warehouse.stat().st_size,
        "path": str(warehouse),
        "specs": specs,
    }
    print(result, flush=True)
    return result


def build_municipality_facts(
    root: Path,
    kaiji_list: list[int] | None = None,
    *,
    sangiin_kaiji: list[int] | None = None,
    write_legacy: bool = True,
    kansai_fill: bool = True,
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
        rows = parse_sangiin_kaiji(root, kaiji, kansai_fill=kansai_fill)
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


def parse_kansai_sangiin_district_pref_facts(root: Path, kaiji: int) -> list[dict]:
    """関西大・選挙区CSVを都道府県×候補に集計し、県区 candidate_votes facts を作る。"""
    path = kansai_csv_path(root, "district", kaiji)
    if path is None:
        return []

    # (prefecture, candidate) -> agg
    buckets: dict[tuple[str, str], dict[str, Any]] = {}
    for item in _read_kansai_csv(path):
        prefecture = clean_text(item.get("都道府県名"))
        name_raw = clean_text(item.get("名前"))
        if not prefecture or not name_raw:
            continue
        cand = compact_name(normalize_person_name(name_raw))
        if not cand:
            continue
        vote = parse_vote(item.get("市区町村別得票数"))
        if vote is None:
            continue
        key = (prefecture, cand)
        bucket = buckets.get(key)
        if bucket is None:
            seats = parse_vote(item.get("定数"))
            rank = parse_vote(item.get("順位"))
            status = compact_name(item.get("現新"))
            buckets[key] = {
                "prefecture": prefecture,
                "candidate": cand,
                "candidate_raw": name_raw,
                "party": compact_name(item.get("党派・会派等")),
                "age": parse_vote(item.get("年齢")),
                "seats": int(seats) if seats is not None else None,
                "rank": int(rank) if rank is not None else None,
                "candidate_status": KANSAI_STATUS_MAP.get(status or ""),
                "votes": 0.0,
            }
            bucket = buckets[key]
        bucket["votes"] += float(vote)

    source_code = f"{KANSAI_SOURCE_PREFIX}-district-pref-{kaiji:02d}"
    rows: list[dict] = []
    for bucket in buckets.values():
        seats = bucket["seats"]
        rank = bucket["rank"]
        if seats is not None and rank is not None:
            elected = rank <= seats
        else:
            elected = None
        rows.append({
            "election_kaiji": kaiji,
            "chamber": "sangiin",
            "election_type": "sangiin",
            "contest": "district",
            "prefecture": bucket["prefecture"],
            "prefecture_code": prefecture_code_of(bucket["prefecture"]),
            "district_number": seats,
            "candidate": bucket["candidate"],
            "candidate_raw": bucket["candidate_raw"],
            "party": bucket["party"],
            "age": int(bucket["age"]) if bucket["age"] is not None else None,
            "candidate_status": bucket["candidate_status"],
            "elected": elected,
            "metric": "candidate_votes",
            "value": bucket["votes"],
            "unit": "votes",
            "source_code": source_code,
            "dataset": f"関西大・参院選DB 選挙区（都道府県集計） 第{kaiji}回",
            "source_url": KANSAI_DB_URL,
            "source_file": path.name,
            "source_sheet": "aggregated",
            "source_cell": f"{bucket['prefecture']}:{bucket['candidate']}",
        })

    # 順位が欠ける場合は得票上位=当選で補完
    by_pref: dict[str, list[dict]] = {}
    for row in rows:
        by_pref.setdefault(row["prefecture"], []).append(row)
    for pref_rows in by_pref.values():
        if all(r["elected"] is not None for r in pref_rows):
            continue
        seats = next((r["district_number"] for r in pref_rows if r["district_number"]), None)
        if not seats:
            continue
        ordered = sorted(pref_rows, key=lambda r: (-(r["value"] or 0), r["candidate"] or ""))
        winners = {id(r) for r in ordered[: int(seats)]}
        for row in pref_rows:
            if row["elected"] is None:
                row["elected"] = id(row) in winners

    print(f"kansai district-pref sangiin {kaiji}: {len(rows)} rows", flush=True)
    return rows


def merge_kansai_district_pref_into_facts(
    root: Path,
    kaiji_list: list[int] | None = None,
) -> dict:
    """既存 facts.parquet に関西大県区（都道府県集計）をマージする。"""
    from soumu_election.warehouse import FACT_COLUMNS, fact_row

    kaiji_list = kaiji_list or list(KANSAI_DISTRICT_PREF_KAIJI)
    warehouse = root / "data" / "warehouse" / "parquet" / "facts.parquet"
    web = root / "web" / "data" / "facts.parquet"
    if not warehouse.exists() and not web.exists():
        raise FileNotFoundError("facts.parquet が見つかりません")
    src = warehouse if warehouse.exists() else web

    new_items: list[dict] = []
    for kaiji in kaiji_list:
        new_items.extend(parse_kansai_sangiin_district_pref_facts(root, kaiji))
    if not new_items:
        return {"added": 0, "kept": 0, "total": 0}

    drop_codes = sorted({item["source_code"] for item in new_items})
    tmp_new = warehouse.parent / "_kansai_district_pref.parquet"
    # fact_row 形式へ
    new_fact_dicts = [dict(zip(FACT_COLUMNS, fact_row(item))) for item in new_items]
    write_parquet(new_fact_dicts, tmp_new)

    con = duckdb.connect()
    code_list = ", ".join("'" + c.replace("'", "''") + "'" for c in drop_codes)
    con.execute(
        f"""
        CREATE OR REPLACE TABLE merged AS
        SELECT * FROM read_parquet(?)
        WHERE source_code IS NULL OR cast(source_code AS VARCHAR) NOT IN ({code_list})
        """,
        [str(src)],
    )
    kept = con.execute("SELECT count(*) FROM merged").fetchone()[0]
    con.execute("INSERT INTO merged BY NAME SELECT * FROM read_parquet(?)", [str(tmp_new)])
    total = con.execute("SELECT count(*) FROM merged").fetchone()[0]
    warehouse.parent.mkdir(parents=True, exist_ok=True)
    con.execute("COPY merged TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(warehouse)])
    # coverage check
    by_kaiji = con.execute("""
        SELECT election_kaiji, count(*)
        FROM merged
        WHERE cast(source_code AS VARCHAR) LIKE 'kansai-district-pref-%'
          AND contest='district' AND metric='candidate_votes'
        GROUP BY 1 ORDER BY 1
    """).fetchall()
    con.close()
    tmp_new.unlink(missing_ok=True)

    web.parent.mkdir(parents=True, exist_ok=True)
    web.write_bytes(warehouse.read_bytes())
    result = {
        "added": len(new_fact_dicts),
        "kept": int(kept),
        "total": int(total),
        "by_kaiji": by_kaiji,
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
    parser.add_argument("--no-kansai-fill", action="store_true", help="関西大二次ソースによる穴埋めをしない")
    parser.add_argument(
        "--merge-kansai-gaps",
        action="store_true",
        help="既存 parquet に参21全面・参22広島など関西大穴埋めをマージ",
    )
    parser.add_argument(
        "--merge-kansai-district-facts",
        action="store_true",
        help="関西大選挙区CSVを都道府県集計し、参院県区facts（21–23）をマージ",
    )
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    if args.merge_kansai_gaps:
        merge_kansai_into_municipality_facts(root)
        return 0
    if args.merge_kansai_district_facts:
        merge_kansai_district_pref_into_facts(root)
        return 0
    build_municipality_facts(
        root,
        args.kaiji,
        sangiin_kaiji=args.sangiin_kaiji,
        write_legacy=not args.no_legacy,
        kansai_fill=not args.no_kansai_fill,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
