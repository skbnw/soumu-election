#!/usr/bin/env python3
"""Create analysis-ready election facts from the lossless raw JSON layer.

v1.2.1:
- 03-07: 党派ヘッダが複数段ある表で、後半党派を誤って前半党派に割り当てないよう修正
v1.2.0:
- 03-11: Excel（第48回）党派別当選人数 + 既存PDFパーサを全回で再適用
- 03-15: 18歳・19歳投票状況（第48回 Excel）
- 03-16: 年齢別投票状況（第45回添付PDF / 第46〜47回PDF本文 / 第48回 Excel）
v1.1.0:
- 03-13 PDF: ヘッダ駆動パーサ（性別列あり/なし・右パネル位置・党派表記差）+ ページ内zigzag読取
- 03-13 XLS: 第48回 Excel（注記行でページ分割し左→右zigzag、括弧書き漢字の次行参照）
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable

import pdfplumber


PREFECTURE = re.compile(r"(?:都|道|府|県)$")


def number(value: Any) -> int | float | None:
    if value is None or value == "" or value in {"-", "－"}:
        return None
    try:
        result = float(str(value).replace(",", "").strip())
    except ValueError:
        return None
    return int(result) if result.is_integer() else result


def compact(value: Any) -> str:
    return re.sub(r"[\s\u3000]+", "", str(value or ""))


PREFECTURES = (
    "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
    "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
    "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県", "岐阜県",
    "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県",
    "奈良県", "和歌山県", "鳥取県", "島根県", "岡山県", "広島県", "山口県",
    "徳島県", "香川県", "愛媛県", "高知県", "福岡県", "佐賀県", "長崎県",
    "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県",
)


def matrix(document: dict[str, Any], sheet: dict[str, Any]) -> list[list[Any]]:
    table = [[None] * sheet["max_column"] for _ in range(sheet["max_row"])]
    for cell in sheet["cells"]:
        table[cell["row"] - 1][cell["column"] - 1] = cell["value"]
    return table


def cell_ref(row: int, column: int) -> str:
    letters = ""
    value = column + 1
    while value:
        value, remainder = divmod(value - 1, 26)
        letters = chr(65 + remainder) + letters
    return f"{letters}{row + 1}"


def base(doc: dict[str, Any], sheet: dict[str, Any], row: int, column: int) -> dict[str, Any]:
    return {
        "election_kaiji": doc["election_kaiji"],
        "source_code": doc.get("source_code") or doc["source_file"].split("_", 1)[0],
        "dataset": doc["dataset"],
        "source_url": doc["source_url"],
        "source_file": doc["source_file"],
        "source_sheet": sheet["name"],
        "source_cell": cell_ref(row, column),
    }


def prefecture_rows(table: list[list[Any]], column: int) -> Iterable[tuple[int, str]]:
    for row_index, row in enumerate(table):
        label = compact(row[column] if column < len(row) else None)
        if PREFECTURE.search(label) or label in {"全国", "計", "合計"}:
            yield row_index, label


def parse_people(doc: dict[str, Any], sheet: dict[str, Any], table: list[list[Any]]) -> list[dict[str, Any]]:
    code = doc.get("source_code", "")
    contest = "smd" if code == "02-01" else "pr" if code == "02-02" else "judicial_review"
    dimensions = 1 if contest != "pr" else 2
    metrics = ("eligible_voters", "voters", "abstentions")
    genders = ("male", "female", "total")
    output = []
    current_block = None
    for row_index, prefecture in prefecture_rows(table, dimensions - 1):
        row = table[row_index]
        if dimensions == 2 and compact(row[0]):
            current_block = compact(row[0])
        for metric_index, metric in enumerate(metrics):
            for gender_index, gender in enumerate(genders):
                column = dimensions + metric_index * 3 + gender_index
                value = number(row[column] if column < len(row) else None)
                if value is None:
                    continue
                fact = base(doc, sheet, row_index, column)
                fact.update({
                    "contest": contest,
                    "scope": "overseas" if "在外" in sheet["name"] else "all",
                    "prefecture": prefecture,
                    "metric": metric,
                    "gender": gender,
                    "value": value,
                    "unit": "people",
                })
                if current_block:
                    fact["pr_block"] = current_block
                output.append(fact)
    return output


def parse_rates(doc: dict[str, Any], sheet: dict[str, Any], table: list[list[Any]]) -> list[dict[str, Any]]:
    code = doc.get("source_code", "")
    contest = "smd" if code == "02-01-02" else "pr" if code == "02-02-02" else "judicial_review"
    dimensions = 1 if contest != "pr" else 2
    metrics = ("turnout_rate", "previous_turnout_rate", "turnout_rate_change")
    genders = ("male", "female", "total")
    output = []
    current_block = None
    for row_index, prefecture in prefecture_rows(table, dimensions - 1):
        row = table[row_index]
        if dimensions == 2 and compact(row[0]):
            current_block = compact(row[0])
        for metric_index, metric in enumerate(metrics):
            for gender_index, gender in enumerate(genders):
                column = dimensions + metric_index * 3 + gender_index
                value = number(row[column] if column < len(row) else None)
                if value is None:
                    continue
                fact = base(doc, sheet, row_index, column)
                fact.update({
                    "contest": contest,
                    "scope": "overseas" if "在外" in sheet["name"] else "all",
                    "prefecture": prefecture,
                    "metric": metric,
                    "gender": gender,
                    "value": value,
                    "unit": "percent",
                })
                if current_block:
                    fact["pr_block"] = current_block
                output.append(fact)
    return output


def parse_ballots(doc: dict[str, Any], sheet: dict[str, Any], table: list[list[Any]]) -> list[dict[str, Any]]:
    code = doc.get("source_code", "")
    contest = "smd" if code == "03-08" else "pr" if code == "03-09" else "judicial_review"
    header_row = next((row for row in table[:8] if any(compact(v) in {"区分", "都道府県"} for v in row)), [])
    pref_column = next((i for i, value in enumerate(header_row) if compact(value) in {"区分", "都道府県"}), 1 if contest == "pr" else 0)
    dimensions = pref_column + 1
    metrics = ("ballots_cast", "valid_ballots", "invalid_ballots", "invalid_ballot_rate")
    output = []
    current_block = None
    for row_index, prefecture in prefecture_rows(table, pref_column):
        row = table[row_index]
        if contest == "pr" and pref_column > 0 and compact(row[pref_column - 1]):
            current_block = compact(row[pref_column - 1])
        for offset, metric in enumerate(metrics):
            column = dimensions + offset
            value = number(row[column] if column < len(row) else None)
            if value is None:
                continue
            fact = base(doc, sheet, row_index, column)
            fact.update({
                "contest": contest,
                "prefecture": prefecture,
                "metric": metric,
                "value": value,
                "unit": "percent" if metric.endswith("rate") else "votes",
            })
            if current_block:
                fact["pr_block"] = current_block
            output.append(fact)
    return output


def parse_ages(doc: dict[str, Any], sheet: dict[str, Any], table: list[list[Any]]) -> list[dict[str, Any]]:
    code = doc.get("source_code", "")
    metric = "candidates" if code == "01-03" else "elected_candidates"
    age_bands = ("25-29", "30-34", "35-39", "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70+", "total")
    output = []
    for row_index, prefecture in prefecture_rows(table, 0):
        row = table[row_index]
        for offset, age_band in enumerate(age_bands, start=1):
            value = number(row[offset] if offset < len(row) else None)
            if value is None:
                continue
            fact = base(doc, sheet, row_index, offset)
            fact.update({
                "contest": "smd",
                "prefecture": prefecture,
                "metric": metric,
                "age_band": age_band,
                "value": value,
                "unit": "people",
            })
            output.append(fact)
    return output


def parse_judicial_votes(doc: dict[str, Any], sheet: dict[str, Any], table: list[list[Any]]) -> list[dict[str, Any]]:
    # Row 3 contains justice names in four-column groups; merged cells mean only
    # the first cell is populated in raw JSON.
    header_row = next((row for row in table[:8] if any(compact(v) in {"区分", "都道府県"} for v in row)), [])
    pref_column = next((i for i, value in enumerate(header_row) if compact(value) in {"区分", "都道府県"}), 0)
    names: dict[int, str] = {}
    for row in table[:5]:
        for column, value in enumerate(row):
            text = compact(value)
            if column > pref_column and text and not any(word in text for word in ("罷免", "投票", "都道府県", "区分", "計")):
                names[column] = text
    starts = sorted(names)
    metrics = ("dismissal_yes", "dismissal_no", "invalid_mark", "review_votes_total")
    output = []
    for row_index, prefecture in prefecture_rows(table, pref_column):
        row = table[row_index]
        for start in starts:
            for offset, metric in enumerate(metrics):
                column = start + offset
                value = number(row[column] if column < len(row) else None)
                if value is None:
                    continue
                fact = base(doc, sheet, row_index, column)
                fact.update({
                    "contest": "judicial_review",
                    "prefecture": prefecture,
                    "justice": names[start],
                    "metric": metric,
                    "value": value,
                    "unit": "votes",
                })
                output.append(fact)
    return output


def parse_judicial_votes_v2(doc: dict[str, Any], sheet: dict[str, Any], table: list[list[Any]]) -> list[dict[str, Any]]:
    """Parse every vertically repeated justice table and reject inconsistent rows."""
    metrics = ("dismissal_yes", "dismissal_no", "invalid_mark", "review_votes_total")
    output = []
    for header_index, header in enumerate(table):
        pref_column = next((i for i, value in enumerate(header)
                            if compact(value) in {"区分", "都道府県"}), None)
        if pref_column is None or header_index == 0:
            continue
        names = {column: compact(value).replace("\ue050", "菅").replace("\ue051", "澤")
                 for column, value in enumerate(table[header_index - 1])
                 if column > pref_column and compact(value)}
        if not names:
            continue
        end = next((i for i in range(header_index + 1, len(table))
                    if any(compact(v) in {"区分", "都道府県"} for v in table[i])), len(table))
        for row_index in range(header_index + 1, end):
            row = table[row_index]
            prefecture = compact(row[pref_column] if pref_column < len(row) else None)
            if prefecture not in PREFECTURES and prefecture not in {"合計", "全国"}:
                continue
            for start, justice in names.items():
                values = [number(row[start + offset] if start + offset < len(row) else None)
                          for offset in range(4)]
                if any(value is None for value in values) or values[0] + values[1] + values[2] != values[3]:
                    continue
                for offset, metric in enumerate(metrics):
                    fact = base(doc, sheet, row_index, start + offset)
                    fact.update({"contest": "judicial_review", "prefecture": prefecture,
                                 "justice": justice, "metric": metric,
                                 "value": values[offset], "unit": "votes"})
                    output.append(fact)
    return output


def pdf_fact_base(doc: dict[str, Any], page: int, row: str) -> dict[str, Any]:
    return {"election_kaiji": doc["election_kaiji"], "source_code": doc["source_code"],
            "dataset": doc["dataset"], "source_url": doc["source_url"],
            "source_file": doc["source_file"], "source_sheet": f"page {page}",
            "source_cell": row}


def parse_pdf_judicial_votes(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize digital PDF tables; accept only rows whose arithmetic balances."""
    metrics = ("dismissal_yes", "dismissal_no", "invalid_mark", "review_votes_total")
    output = []
    pua = {"\ue042": "那", "\ue06e": "橋"}
    for page in doc.get("pages", []):
        lines = page.get("text", "").splitlines()
        name_line = next((line for line in reversed(lines)
                          if not re.search(r"\d", line) and "　" in line), "")
        for old, new in pua.items():
            name_line = name_line.replace(old, new)
        names = [compact(value) for value in re.split(r" +", name_line.strip()) if compact(value)]
        rows, current = {}, None
        for line in lines:
            match = re.match(r"^\s*(\d{1,2})\s+", line)
            if match and 1 <= int(match.group(1)) <= 47:
                current = int(match.group(1))
                rows[current] = line
            elif current is not None and not re.match(r"^\s*(?:合\s*計|\d{1,2}\s+)", line):
                rows[current] += line.strip()
        for index, prefecture in enumerate(PREFECTURES, 1):
            numbers = [int(value.replace(",", ""))
                       for value in re.findall(r"\d[\d,]*", rows.get(index, ""))]
            if numbers and numbers[0] == index:
                numbers = numbers[1:]
            if len(numbers) not in {4, 8} or len(numbers) // 4 != len(names):
                continue
            for justice_index, justice in enumerate(names):
                values = numbers[justice_index * 4:justice_index * 4 + 4]
                if values[0] + values[1] + values[2] != values[3]:
                    continue
                for offset, metric in enumerate(metrics):
                    fact = pdf_fact_base(doc, page["page"], f"prefecture:{index}:justice:{justice_index + 1}")
                    fact.update({"contest": "judicial_review", "prefecture": prefecture,
                                 "justice": justice, "metric": metric,
                                 "value": values[offset], "unit": "votes"})
                    output.append(fact)
        # Match the workbook convention by adding a derived national total.
        for justice in names:
            justice_rows = [fact for fact in output
                            if fact["source_sheet"] == f"page {page['page']}" and fact["justice"] == justice]
            for metric in metrics:
                values = [fact["value"] for fact in justice_rows if fact["metric"] == metric]
                if len(values) != 47:
                    continue
                fact = pdf_fact_base(doc, page["page"], f"total:justice:{justice}")
                fact.update({"contest": "judicial_review", "prefecture": "合計",
                             "justice": justice, "metric": metric,
                             "value": sum(values), "unit": "votes"})
                output.append(fact)
    return output


def party_headers(row: list[Any], start: int, width: int) -> list[tuple[int, str]]:
    return [(column, compact(row[column])) for column in range(start, len(row), width) if compact(row[column])]


def parse_party_status_gender(doc: dict[str, Any], sheet: dict[str, Any], table: list[list[Any]]) -> list[dict[str, Any]]:
    """Party x incumbency x gender tables (01-01 and 03-01)."""
    header_index = next(i for i, row in enumerate(table) if len(party_headers(row, 2, 3)) >= 2)
    parties = party_headers(table[header_index], 2, 3)
    gender_index = next(i for i in range(header_index + 1, min(header_index + 5, len(table))) if compact(table[i][2]) == "男")
    metric = "candidates" if doc["source_code"] == "01-01" else "elected_candidates"
    genders = ("male", "female", "total")
    status_map = {"新": "new", "前": "incumbent", "元": "former", "計": "total"}
    contest = None
    previous_status = None
    output = []
    for row_index in range(gender_index + 1, len(table)):
        row = table[row_index]
        raw_contest = compact(row[0])
        if raw_contest:
            contest = "smd" if "小選挙区" in raw_contest else "pr" if "比例代表" in raw_contest else "all" if "合計" in raw_contest else contest
        raw_status = compact(row[1])
        if raw_status in status_map:
            previous_status = status_map[raw_status]
            variant = "main"
        elif previous_status and any(number(v) is not None for v in row[2:]):
            variant = "supplemental"
        else:
            continue
        for start, party in parties:
            for offset, gender in enumerate(genders):
                column = start + offset
                value = number(row[column] if column < len(row) else None)
                if value is None:
                    continue
                fact = base(doc, sheet, row_index, column)
                fact.update({"contest": contest, "party": party, "candidate_status": previous_status,
                             "row_variant": variant, "metric": metric, "gender": gender,
                             "value": value, "unit": "people"})
                output.append(fact)
    return output


def parse_prefecture_party_status(doc: dict[str, Any], sheet: dict[str, Any], table: list[list[Any]]) -> list[dict[str, Any]]:
    header_index = next(i for i, row in enumerate(table) if len(party_headers(row, 2, 4)) >= 2)
    parties = party_headers(table[header_index], 2, 4)
    status_index = next(i for i in range(header_index + 1, min(header_index + 5, len(table))) if compact(table[i][2]) == "新")
    metric = "candidates" if doc["source_code"] == "01-02" else "elected_candidates"
    statuses = ("new", "incumbent", "former", "total")
    output = []
    for row_index, prefecture in prefecture_rows(table, 0):
        if row_index <= status_index:
            continue
        row = table[row_index]
        for start, party in parties:
            for offset, status in enumerate(statuses):
                column = start + offset
                value = number(row[column] if column < len(row) else None)
                if value is None:
                    continue
                fact = base(doc, sheet, row_index, column)
                fact.update({"contest": "smd", "prefecture": prefecture, "party": party,
                             "candidate_status": status, "metric": metric, "value": value, "unit": "people"})
                output.append(fact)
    return output


def parse_party_comparison(doc: dict[str, Any], sheet: dict[str, Any], table: list[list[Any]]) -> list[dict[str, Any]]:
    contest = "smd" if doc["source_code"] == "03-04" else "pr"
    row_metrics = {2: ("current_votes", "votes"), 4: ("current_vote_share", "ratio"),
                   5: ("previous_votes", "votes"), 7: ("previous_vote_share", "ratio"),
                   8: ("vote_change", "votes"), 10: ("vote_change_rate", "ratio")}
    output = []
    for header_index, row in enumerate(table):
        if compact(row[0]) != "区分":
            continue
        parties = [(c, compact(v)) for c, v in enumerate(row[1:], start=1) if compact(v)]
        for relative, (metric, unit) in row_metrics.items():
            row_index = header_index + relative
            if row_index >= len(table):
                continue
            for column, party in parties:
                value = number(table[row_index][column] if column < len(table[row_index]) else None)
                if value is None:
                    continue
                fact = base(doc, sheet, row_index, column)
                fact.update({"contest": contest, "party": party, "metric": metric,
                             "value": value, "unit": unit})
                output.append(fact)
    return output


def parse_prefecture_party_gender(doc: dict[str, Any], sheet: dict[str, Any], table: list[list[Any]]) -> list[dict[str, Any]]:
    header_index = next((i for i, row in enumerate(table) if len(party_headers(row, 1, 3)) >= 2), None)
    if header_index is None:
        return []
    parties = party_headers(table[header_index], 1, 3)
    gender_index = next((i for i in range(header_index + 1, min(header_index + 5, len(table))) if compact(table[i][1]) == "男"), None)
    if gender_index is None:
        return []
    output = []
    for row_index, prefecture in prefecture_rows(table, 0):
        if row_index <= gender_index:
            continue
        row = table[row_index]
        for start, party in parties:
            for offset, gender in enumerate(("male", "female", "total")):
                column = start + offset
                value = number(row[column] if column < len(row) else None)
                if value is None:
                    continue
                fact = base(doc, sheet, row_index, column)
                fact.update({"contest": "smd", "prefecture": prefecture, "party": party,
                             "gender": gender, "metric": "party_votes", "value": value, "unit": "votes"})
                output.append(fact)
    return output


def parse_pr_prefecture_party(doc: dict[str, Any], sheet: dict[str, Any], table: list[list[Any]]) -> list[dict[str, Any]]:
    """Normalize 03-07. Party headers may repeat when the sheet continues with more parties."""
    output, current_block, parties = [], None, []
    for row_index, row in enumerate(table):
        header_label = compact(row[1] if len(row) > 1 else None)
        if header_label in {"都道府県", "区分"} and any(compact(v) for v in row[2:]):
            parties = [(c, compact(v)) for c, v in enumerate(row[2:], start=2) if compact(v)]
            continue
        if not parties:
            continue
        if compact(row[0] if row else None):
            current_block = compact(row[0])
        prefecture = compact(row[1] if len(row) > 1 else None)
        if not (PREFECTURE.search(prefecture) or prefecture in {"計", "合計", "全国"}):
            continue
        for column, party in parties:
            value = number(row[column] if column < len(row) else None)
            if value is None:
                continue
            fact = base(doc, sheet, row_index, column)
            fact.update({"contest": "pr", "pr_block": current_block, "prefecture": prefecture,
                         "party": party, "metric": "party_votes", "value": value, "unit": "votes"})
            output.append(fact)
    return output


def pr_block_name(value: Any) -> str | None:
    text = compact(value).strip("＜＞<>")
    return text if text.endswith("選挙区") else None


def parse_pr_block_ranking(doc: dict[str, Any], sheet: dict[str, Any], table: list[list[Any]]) -> list[dict[str, Any]]:
    output = []
    for heading_row, row in enumerate(table):
        for heading_column, value in enumerate(row):
            block = pr_block_name(value)
            if not block:
                continue
            start = max(0, heading_column - 1)
            header_row = next((r for r in range(heading_row + 1, min(heading_row + 5, len(table)))
                               if start + 3 < len(table[r]) and compact(table[r][start]) == "順位"), None)
            if header_row is None:
                continue
            for row_index in range(header_row + 1, min(header_row + 55, len(table))):
                if row_index > heading_row + 1 and heading_column < len(table[row_index]) and pr_block_name(table[row_index][heading_column]):
                    break
                rank = number(table[row_index][start] if start < len(table[row_index]) else None)
                party = compact(table[row_index][start + 1] if start + 1 < len(table[row_index]) else None)
                votes = number(table[row_index][start + 2] if start + 2 < len(table[row_index]) else None)
                rate = number(table[row_index][start + 3] if start + 3 < len(table[row_index]) else None)
                if not party or rank is None:
                    continue
                for column, metric, metric_value, unit in ((start, "party_rank", rank, "rank"),
                                                           (start + 2, "party_votes", votes, "votes"),
                                                           (start + 3, "party_vote_share", rate, "percent")):
                    if metric_value is None:
                        continue
                    fact = base(doc, sheet, row_index, column)
                    fact.update({"contest": "pr", "pr_block": block, "party": party,
                                 "metric": metric, "value": metric_value, "unit": unit})
                    output.append(fact)
    return output


def parse_seat_allocation(doc: dict[str, Any], sheet: dict[str, Any], table: list[list[Any]]) -> list[dict[str, Any]]:
    output = []
    headings = [(r, c, pr_block_name(v)) for r, row in enumerate(table) for c, v in enumerate(row) if pr_block_name(v)]
    for heading_row, heading_col, block in headings:
        party_row = next((r for r in range(heading_row + 1, min(heading_row + 6, len(table)))
                          if sum(bool(compact(v)) for v in table[r]) >= 2 and any("党" in compact(v) or compact(v) in {"諸派", "無所属", "チームみらい", "中道改革連合"} for v in table[r])), None)
        if party_row is None:
            continue
        rank_row = next((r for r in range(party_row + 1, min(party_row + 4, len(table)))
                         if any(compact(v) == "順位" for v in table[r])), None)
        if rank_row is None:
            continue
        parties = []
        for rank_column, value in enumerate(table[rank_row]):
            if compact(value) != "順位":
                continue
            party = compact(table[party_row][rank_column])
            if not party and rank_column + 1 < len(table[party_row]):
                party = compact(table[party_row][rank_column + 1])
            if party:
                parties.append((rank_column, party))
        data_start = rank_row + 1
        for row_index in range(data_start, min(data_start + 50, len(table))):
            divisor = number(table[row_index][max(0, heading_col - 1)] if max(0, heading_col - 1) < len(table[row_index]) else None)
            if divisor is None:
                continue
            for rank_column, party in parties:
                rank = number(table[row_index][rank_column] if rank_column < len(table[row_index]) else None)
                quotient = number(table[row_index][rank_column + 1] if rank_column + 1 < len(table[row_index]) else None)
                if quotient is None:
                    continue
                fact = base(doc, sheet, row_index, rank_column + 1)
                fact.update({"contest": "pr", "pr_block": block, "party": party, "divisor": divisor,
                             "allocation_rank": rank, "metric": "dhondt_quotient", "value": quotient, "unit": "quotient"})
                output.append(fact)
    return output


PDF_SUMMARY_CODES = {"02-01", "02-02", "02-03", "03-08", "03-09", "05-01", "05-03"}
PDF_REMAINING_CODES = {"03-10", "03-11", "03-12", "03-13"}
PDF_PARTY_STATUS_CODES = {"01-01", "03-01"}
PDF_PARTY_COMPARISON_CODES = {"03-04", "03-05"}
PDF_GEOMETRIC_CODES = {"01-02", "01-03", "03-02", "03-03", "03-06", "03-07"}


def expand_pdf_table(table: list[list[Any]]) -> list[list[Any]]:
    """Expand pdfplumber cells containing several visual rows into normal rows."""
    output: list[list[Any]] = []
    for row in table:
        columns = [str(value).splitlines() if value is not None else [""] for value in row]
        height = max(len(values) for values in columns)
        for line_index in range(height):
            output.append([values[line_index] if line_index < len(values) else None for values in columns])
    return output


def validated_pdf_table(table: list[list[Any]], kind: str, pref_column: int) -> list[list[Any]]:
    """Blank inconsistent data rows so existing parsers cannot emit them."""
    cleaned = [list(row) for row in table]
    for row in cleaned:
        label = compact(row[pref_column] if pref_column < len(row) else None)
        if label not in PREFECTURES and label not in {"計", "合計", "全国"}:
            continue
        start = pref_column + 1
        values = [number(value) for value in row[start:]]
        valid = False
        if kind == "people" and len(values) >= 9 and all(value is not None for value in values[:9]):
            valid = (all(values[i] + values[i + 1] == values[i + 2] for i in (0, 3, 6))
                     and all(values[i] == values[i + 3] + values[i + 6] for i in range(3)))
        elif kind == "rates" and len(values) >= 9 and all(value is not None for value in values[:9]):
            valid = all(abs(values[i] - values[i + 3] - values[i + 6]) <= 0.02 for i in range(3))
        elif kind == "ballots" and len(values) >= 4 and all(value is not None for value in values[:4]):
            expected_rate = values[2] / values[0] * 100 if values[0] else 0
            valid = values[0] == values[1] + values[2] and abs(expected_rate - values[3]) <= 0.011
        if not valid:
            row[pref_column] = None
    return cleaned


def parse_pdf_summary(doc: dict[str, Any], pdf_path: Path) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_index, page in enumerate(pdf.pages, 1):
            tables = page.extract_tables()
            if not tables:
                continue
            table = expand_pdf_table(tables[0])
            sheet = {"name": f"page {page_index}"}
            code = doc["source_code"]
            if code == "03-08":
                # The PDF has a separate sequence-number column absent from the fact schema.
                adjusted = []
                for row in table:
                    if not compact(row[1] if len(row) > 1 else None) and compact(row[0]) in {"計", "合計"}:
                        row[1] = row[0]
                    adjusted.append(row[1:])
                table = adjusted
            if code in {"02-01", "02-02", "02-03", "05-01"}:
                kind = "people" if page_index == 1 else "rates"
                pref_column = 1 if code in {"02-02", "02-03"} else 0
                parsed_doc = dict(doc)
                if code == "02-03":
                    parsed_doc["source_code"] = "02-02" if kind == "people" else "02-02-02"
                elif kind == "rates" and code in {"02-01", "02-02"}:
                    parsed_doc["source_code"] = f"{code}-02"
                parser = parse_people if kind == "people" else parse_rates
            else:
                kind = "ballots"
                pref_column = 1 if code == "03-09" else 0
                parsed_doc = doc
                parser = parse_ballots
            table = validated_pdf_table(table, kind, pref_column)
            records = parser(parsed_doc, sheet, table)
            for record in records:
                record["source_code"] = code
                if code == "02-03":
                    record["scope"] = "overseas"
                record["source_cell"] = f"pdf-table:{record['source_cell']}"
            output.extend(records)
    return output


def pdf_cell_numbers(value: Any) -> tuple[int | float | None, int | float | None]:
    text = str(value or "")
    lines = text.splitlines()
    main = number(lines[0]) if lines else None
    match = re.search(r"\(([^)]*)\)", text, re.DOTALL)
    supplemental = number(compact(match.group(1))) if match else None
    return main, supplemental


def parse_pdf_party_status(doc: dict[str, Any], pdf_path: Path) -> list[dict[str, Any]]:
    metric = "candidates" if doc["source_code"] == "01-01" else "elected_candidates"
    status_map = {"新": "new", "前": "incumbent", "元": "former", "計": "total"}
    output: list[dict[str, Any]] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_index, page in enumerate(pdf.pages, 1):
            table = page.extract_tables()[0]
            if page_index == 3:
                table[0][2], table[0][5], table[0][8] = "その他・政党等所属", "無所属", "その他小計"
            parties = {column: compact(table[0][column]) for column in range(2, len(table[0]), 3)
                       if compact(table[0][column])}
            contest = None
            for row_index, row in enumerate(table[2:], 2):
                label = compact(row[0])
                if label:
                    if label == "小選挙区": contest = "smd"
                    elif label == "比例代表": contest = "pr"
                    elif label in {"候補者数計", "合計"}: contest = "all"
                status = status_map.get(compact(row[1]))
                if contest is None or status is None:
                    continue
                for start, party in parties.items():
                    cells = [pdf_cell_numbers(row[start + offset] if start + offset < len(row) else None)
                             for offset in range(3)]
                    for variant_index, variant in enumerate(("main", "supplemental")):
                        values = [cell[variant_index] for cell in cells]
                        numeric = [0 if value is None else value for value in values]
                        if numeric[0] + numeric[1] != numeric[2]:
                            continue
                        for offset, gender in enumerate(("male", "female", "total")):
                            if values[offset] is None:
                                continue
                            fact = pdf_fact_base(doc, page_index, f"table:R{row_index + 1}C{start + offset + 1}")
                            fact.update({"contest": contest, "party": party, "candidate_status": status,
                                         "row_variant": variant, "metric": metric, "gender": gender,
                                         "value": values[offset], "unit": "people"})
                            output.append(fact)
    return output


def comparison_value(value: Any) -> tuple[int | float | None, int | float | None]:
    text = str(value or "")
    lines = text.splitlines()
    votes = number(lines[0]) if lines else None
    match = re.search(r"\(([^)]*)\)", text, re.DOTALL)
    share = number(compact(match.group(1))) if match else None
    return votes, share


def parse_pdf_party_comparison(doc: dict[str, Any], pdf_path: Path) -> list[dict[str, Any]]:
    contest = "smd" if doc["source_code"] == "03-04" else "pr"
    rows: list[tuple[str, tuple[Any, Any], tuple[Any, Any], tuple[Any, Any], int, int]] = []
    with pdfplumber.open(pdf_path) as pdf:
        for table_index, table in enumerate(pdf.pages[0].extract_tables(), 1):
            for column, party_raw in enumerate(table[0][1:], 1):
                party = compact(party_raw)
                if not party:
                    continue
                rows.append((party, comparison_value(table[1][column]),
                             comparison_value(table[2][column]), comparison_value(table[3][column]),
                             table_index, column))
    total = next((row for row in rows if row[0] == "合計"), None)
    parties = [row for row in rows if row[0] != "合計"]
    if total is None or total[1][0] is None:
        return []
    current_sum = sum(row[1][0] or 0 for row in parties)
    if abs(current_sum - total[1][0]) > 0.01:
        return []
    output: list[dict[str, Any]] = []
    definitions = ((0, 0, "current_votes", "votes"), (0, 1, "current_vote_share", "percent"),
                   (1, 0, "previous_votes", "votes"), (1, 1, "previous_vote_share", "percent"),
                   (2, 0, "vote_change", "votes"), (2, 1, "vote_change_rate", "percent"))
    for party, current, previous, change, table_index, column in rows:
        groups = (current, previous, change)
        for group_index, value_index, metric, unit in definitions:
            value = groups[group_index][value_index]
            if value is None:
                continue
            fact = pdf_fact_base(doc, 1, f"table:{table_index}:column:{column + 1}:{metric}")
            fact.update({"contest": contest, "party": party, "metric": metric,
                         "value": value, "unit": unit})
            output.append(fact)
    return output


def pdf_lines(page: Any, bbox: Any) -> list[dict[str, Any]]:
    if bbox is None:
        return []
    # Some old PDFs leak zero-height characters from the preceding merged row
    # into the next cell. Ignore clipped glyphs and rebuild lines by y position.
    chars = [char for char in page.crop(bbox).chars if char["bottom"] - char["top"] > 1]
    groups: list[list[dict[str, Any]]] = []
    for char in sorted(chars, key=lambda item: (item["top"], item["x0"])):
        target = next((group for group in groups if abs(group[0]["top"] - char["top"]) <= 0.6), None)
        if target is None:
            target = []
            groups.append(target)
        target.append(char)
    return [{"top": min(char["top"] for char in group),
             "text": "".join(char["text"] for char in sorted(group, key=lambda item: item["x0"]))}
            for group in groups]


def line_at(lines: list[dict[str, Any]], top: float, tolerance: float = 2.5) -> str | None:
    candidates = [(abs(line["top"] - top), compact(line["text"])) for line in lines]
    return min(candidates)[1] if candidates and min(candidates)[0] <= tolerance else None


def parse_pdf_age_table(doc: dict[str, Any], page: Any) -> list[dict[str, Any]]:
    metric = "candidates" if doc["source_code"] == "01-03" else "elected_candidates"
    age_bands = ("25-29", "30-34", "35-39", "40-44", "45-49", "50-54",
                 "55-59", "60-64", "65-69", "70+", "total")
    output = []
    table = page.find_tables()[0]
    for structural_index, structural_row in enumerate(table.rows[1:], 1):
        anchors = pdf_lines(page, structural_row.cells[0])
        columns = [pdf_lines(page, bbox) for bbox in structural_row.cells[1:12]]
        for anchor_index, anchor in enumerate(anchors, 1):
            prefecture = compact(anchor["text"])
            if prefecture not in PREFECTURES and prefecture not in {"計", "合計"}:
                continue
            values = [number(line_at(lines, anchor["top"])) for lines in columns]
            if values[-1] is None or sum(value or 0 for value in values[:-1]) != values[-1]:
                continue
            for column, (age_band, value) in enumerate(zip(age_bands, values), 1):
                if value is None:
                    continue
                fact = pdf_fact_base(doc, 1, f"geometry:R{structural_index + 1}:{anchor_index}:C{column + 1}")
                fact.update({"contest": "smd", "prefecture": prefecture, "metric": metric,
                             "age_band": age_band, "value": value, "unit": "people"})
                output.append(fact)
    return output


def parse_pdf_prefecture_party_gender(doc: dict[str, Any], pdf_path: Path) -> list[dict[str, Any]]:
    output = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_index, page in enumerate(pdf.pages, 1):
            table = page.find_tables()[0]
            header = page.extract_tables()[0][0]
            parties = {column: compact(header[column]) for column in range(1, len(header), 3)
                       if compact(header[column])}
            for structural_index, structural_row in enumerate(table.rows[2:], 2):
                anchors = pdf_lines(page, structural_row.cells[0])
                column_lines = [pdf_lines(page, bbox) for bbox in structural_row.cells]
                for anchor_index, anchor in enumerate(anchors, 1):
                    prefecture = compact(anchor["text"])
                    if prefecture not in PREFECTURES and prefecture not in {"計", "合計"}:
                        continue
                    for start, party in parties.items():
                        values = [number(line_at(column_lines[start + offset], anchor["top"])) for offset in range(3)]
                        numeric = [value or 0 for value in values]
                        if numeric[0] + numeric[1] != numeric[2]:
                            continue
                        for offset, gender in enumerate(("male", "female", "total")):
                            if values[offset] is None:
                                continue
                            fact = pdf_fact_base(doc, page_index,
                                                 f"geometry:R{structural_index + 1}:{anchor_index}:C{start + offset + 1}")
                            fact.update({"contest": "smd", "prefecture": prefecture, "party": party,
                                         "gender": gender, "metric": "party_votes",
                                         "value": values[offset], "unit": "votes"})
                            output.append(fact)
    return output


def parse_pdf_pr_prefecture_party(doc: dict[str, Any], pdf_path: Path) -> list[dict[str, Any]]:
    output = []
    groups = (
        ("北海道", ("北海道",)),
        ("東北", ("青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県", "計")),
        ("北関東", ("茨城県", "栃木県", "群馬県", "埼玉県", "計")),
        ("南関東", ("千葉県", "神奈川県", "山梨県", "計")),
        ("東京都", ("東京都",)),
        ("北陸信越", ("新潟県", "富山県", "石川県", "福井県", "長野県", "計")),
        ("東海", ("岐阜県", "静岡県", "愛知県", "三重県", "計")),
        ("近畿", ("滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県", "計")),
        ("中国", ("鳥取県", "島根県", "岡山県", "広島県", "山口県", "計")),
        ("四国", ("徳島県", "香川県", "愛媛県", "高知県", "計")),
        ("九州", ("福岡県", "佐賀県", "長崎県", "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県", "計")),
        ("全国", ("合計",)),
    )
    with pdfplumber.open(pdf_path) as pdf:
        for page_index, page in enumerate(pdf.pages, 1):
            extracted = page.extract_tables()[0]
            table = page.find_tables()[0]
            parties = {column: compact(extracted[0][column]) for column in range(2, len(extracted[0]))
                       if compact(extracted[0][column])}
            for structural_index, structural_row in enumerate(table.rows[1:], 1):
                block, expected_labels = groups[structural_index - 1]
                anchors = pdf_lines(page, structural_row.cells[1])
                column_lines = [pdf_lines(page, bbox) for bbox in structural_row.cells]
                if len(anchors) != len(expected_labels):
                    continue
                for anchor_index, (anchor, prefecture) in enumerate(zip(anchors, expected_labels), 1):
                    for column, party in parties.items():
                        value = number(line_at(column_lines[column], anchor["top"]))
                        if value is None:
                            continue
                        fact = pdf_fact_base(doc, page_index,
                                             f"geometry:R{structural_index + 1}:{anchor_index}:C{column + 1}")
                        fact.update({"contest": "pr", "pr_block": block, "prefecture": prefecture,
                                     "party": party, "metric": "party_votes",
                                     "value": value, "unit": "votes"})
                        output.append(fact)
    totals = {(fact["pr_block"], fact["prefecture"]): fact["value"] for fact in output if fact["party"] == "合計"}
    invalid = set()
    for key, total in totals.items():
        party_sum = sum(fact["value"] for fact in output
                        if (fact["pr_block"], fact["prefecture"]) == key and fact["party"] != "合計")
        if party_sum != total:
            invalid.add(key)
    return [fact for fact in output if (fact["pr_block"], fact["prefecture"]) not in invalid]


def packed_status_values(page: Any, bbox: Any, top: float) -> list[int | float | None]:
    if bbox is None:
        return [None] * 4
    x0, _, x1, _ = bbox
    buckets = [[], [], [], []]
    for char in page.crop(bbox).chars:
        if char["bottom"] - char["top"] <= 1 or abs(char["top"] - top) > 2.5:
            continue
        center = (char["x0"] + char["x1"]) / 2
        index = min(3, max(0, int((center - x0) / (x1 - x0) * 4)))
        buckets[index].append(char)
    return [number("".join(char["text"] for char in sorted(bucket, key=lambda item: item["x0"])))
            for bucket in buckets]


def parse_pdf_prefecture_party_status(doc: dict[str, Any], pdf_path: Path) -> list[dict[str, Any]]:
    metric = "candidates" if doc["source_code"] == "01-02" else "elected_candidates"
    statuses = ("new", "incumbent", "former", "total")
    output = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_index, page in enumerate(pdf.pages, 1):
            extracted = page.extract_tables()[0]
            table = page.find_tables()[0]
            if page_index == 1:
                header_rows = 2
                parties = {column: compact(extracted[0][column]) for column in range(2, len(extracted[0]))
                           if compact(extracted[0][column])}
            else:
                header_rows = 3
                parties = {2: "その他・政党等所属", 3: "無所属", 4: "その他小計", 5: "合計"}
            for structural_index, structural_row in enumerate(table.rows[header_rows:], header_rows):
                anchors = pdf_lines(page, structural_row.cells[0])
                for anchor_index, anchor in enumerate(anchors, 1):
                    prefecture = compact(anchor["text"])
                    if prefecture not in PREFECTURES and prefecture not in {"計", "合計"}:
                        continue
                    for column, party in parties.items():
                        values = packed_status_values(page, structural_row.cells[column], anchor["top"])
                        numeric = [value or 0 for value in values]
                        if numeric[0] + numeric[1] + numeric[2] != numeric[3]:
                            continue
                        for offset, status in enumerate(statuses):
                            if values[offset] is None:
                                continue
                            fact = pdf_fact_base(doc, page_index,
                                                 f"geometry:R{structural_index + 1}:{anchor_index}:C{column + 1}:{offset + 1}")
                            fact.update({"contest": "smd", "prefecture": prefecture, "party": party,
                                         "candidate_status": status, "metric": metric,
                                         "value": values[offset], "unit": "people"})
                            output.append(fact)
    return output


def parse_pdf_geometric(doc: dict[str, Any], pdf_path: Path) -> list[dict[str, Any]]:
    if doc["source_code"] in {"01-02", "03-02"}:
        return parse_pdf_prefecture_party_status(doc, pdf_path)
    if doc["source_code"] in {"01-03", "03-03"}:
        with pdfplumber.open(pdf_path) as pdf:
            return parse_pdf_age_table(doc, pdf.pages[0])
    if doc["source_code"] == "03-06":
        return parse_pdf_prefecture_party_gender(doc, pdf_path)
    if doc["source_code"] == "03-07":
        return parse_pdf_pr_prefecture_party(doc, pdf_path)
    return []


def page_pr_block(page: Any) -> str:
    match = re.search(r"[＜<]([^＞>]+?)選挙区[＞>]", page.extract_text() or "")
    if not match:
        match = re.search(r"^([^\n]+?)選挙区$", page.extract_text() or "", re.MULTILINE)
    return compact(match.group(1)) if match else ""


def parse_pdf_pr_ranking(doc: dict[str, Any], pdf_path: Path) -> list[dict[str, Any]]:
    output = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_index, page in enumerate(pdf.pages, 1):
            block = page_pr_block(page)
            table = page.extract_tables()[0]
            for row_index, row in enumerate(table[1:], 2):
                for start in (0, 4, 8):
                    rank, party = number(row[start]), compact(row[start + 1])
                    votes, share = number(row[start + 2]), number(row[start + 3])
                    if rank is None or not party:
                        continue
                    for column, metric, value, unit in ((start, "party_rank", rank, "rank"),
                                                        (start + 2, "party_votes", votes, "votes"),
                                                        (start + 3, "party_vote_share", share, "percent")):
                        if value is None:
                            continue
                        fact = pdf_fact_base(doc, page_index, f"table:R{row_index}C{column + 1}")
                        fact.update({"contest": "pr", "pr_block": block, "party": party,
                                     "metric": metric, "value": value, "unit": unit})
                        output.append(fact)
    return output


def clean_count(value: Any) -> int | float | None:
    match = re.search(r"-?[\d,.]+", str(value or ""))
    return number(match.group(0)) if match else None


def parse_pdf_pr_elected(doc: dict[str, Any], pdf_path: Path) -> list[dict[str, Any]]:
    output = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_index, page in enumerate(pdf.pages, 1):
            block = page_pr_block(page)
            table = page.extract_tables()[0]
            for start in (0, 7, 14, 21):
                party = compact(table[0][start + 2] if start + 2 < len(table[0]) else None)
                if not party:
                    continue
                votes = clean_count(table[1][start + 2])
                counts = {"total": clean_count(table[2][start + 2]),
                          "male": clean_count(table[3][start + 1]),
                          "female": clean_count(table[3][start + 4])}
                if votes is not None:
                    fact = pdf_fact_base(doc, page_index, f"table:party:{start + 1}:votes")
                    fact.update({"contest": "pr", "pr_block": block, "party": party,
                                 "metric": "party_votes", "value": votes, "unit": "votes"})
                    output.append(fact)
                if all(value is not None for value in counts.values()) and counts["male"] + counts["female"] == counts["total"]:
                    for gender, value in counts.items():
                        fact = pdf_fact_base(doc, page_index, f"table:party:{start + 1}:elected:{gender}")
                        fact.update({"contest": "pr", "pr_block": block, "party": party,
                                     "gender": gender, "metric": "elected_candidates",
                                     "value": value, "unit": "people"})
                        output.append(fact)
                positions = str(table[5][start] or "").splitlines()
                names = str(table[5][start + 1] or "").splitlines()
                if len(positions) == len(names):
                    for list_index, (position, name) in enumerate(zip(positions, names), 1):
                        value = number(position)
                        if value is None or not compact(name):
                            continue
                        fact = pdf_fact_base(doc, page_index, f"table:party:{start + 1}:list:{list_index}")
                        fact.update({"contest": "pr", "pr_block": block, "party": party,
                                     "candidate": compact(name), "candidate_raw": name,
                                     "metric": "pr_list_position", "value": value, "unit": "rank"})
                        output.append(fact)
    return output


def parse_pdf_seat_allocation(doc: dict[str, Any], pdf_path: Path) -> list[dict[str, Any]]:
    output = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_index, page in enumerate(pdf.pages, 1):
            block = page_pr_block(page)
            extracted, table = page.extract_tables()[0], page.find_tables()[0]
            data_row = table.rows[2]
            divisor_lines = pdf_lines(page, data_row.cells[0])
            for start in range(1, len(extracted[0]) - 1, 2):
                party = compact(str(extracted[0][start] or "").replace("順位", ""))
                if not party:
                    continue
                rank_lines = pdf_lines(page, data_row.cells[start])
                quotient_lines = pdf_lines(page, data_row.cells[start + 1])
                for divisor_index, anchor in enumerate(divisor_lines, 1):
                    divisor = number(anchor["text"])
                    quotient = number(line_at(quotient_lines, anchor["top"]))
                    rank = number(line_at(rank_lines, anchor["top"]))
                    if divisor is None or quotient is None:
                        continue
                    fact = pdf_fact_base(doc, page_index, f"geometry:party:{start}:divisor:{divisor_index}")
                    fact.update({"contest": "pr", "pr_block": block, "party": party,
                                 "divisor": divisor, "allocation_rank": rank,
                                 "metric": "dhondt_quotient", "value": quotient, "unit": "quotient"})
                    output.append(fact)
    return output


def candidate_name(value: Any) -> tuple[str, str]:
    raw = str(value or "").strip()
    parenthetical = re.findall(r"\(([^)]+)\)", raw)
    if parenthetical:
        return compact(parenthetical[-1]), raw
    lines = [compact(line) for line in raw.splitlines() if compact(line)]
    return (lines[-1] if lines else ""), raw


def smd_candidate_panel_starts(header: list[Any]) -> list[int]:
    return [index for index, value in enumerate(header) if compact(value) == "当落"]


def smd_candidate_offsets(header: list[Any], start: int) -> dict[str, int | None]:
    """Map logical fields to offsets from a 当落 column using the panel header."""
    end = next((index for index in smd_candidate_panel_starts(header) if index > start), len(header))
    labels = {compact(header[index]): index - start for index in range(start, end)}
    has_gender = "性別" in labels
    return {
        "name": labels.get("候補者氏名", 1),
        "gender": labels.get("性別"),
        "age": labels.get("年齢", 2 if not has_gender else 3),
        "party": next((labels[key] for key in ("届出政党等", "党派") if key in labels), 3 if not has_gender else 4),
        "status": next((labels[key] for key in ("新前元別", "新前") if key in labels), 4 if not has_gender else 5),
        "occupation": labels.get("職業", 5 if not has_gender else 6),
        "votes": labels.get("得票数", 6 if not has_gender else 7),
        "dual": labels.get("重複", 7 if not has_gender else 8),
        "sekihairitsu": next((labels[key] for key in ("惜敗率(%)", "惜敗率") if key in labels), 8 if not has_gender else 9),
    }


def parse_smd_candidate_panels(
    rows: Iterable[tuple[int, list[Any]]],
    *,
    header: list[Any],
    make_fact,
    state: dict[int, dict[str, Any]] | None = None,
    name_lookup: Any | None = None,
) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]]]:
    """Shared SMD candidate table parser for PDF and Excel panels."""
    output: list[dict[str, Any]] = []
    status_map = {"新": "new", "前": "incumbent", "元": "former"}
    starts = smd_candidate_panel_starts(header) or [0]
    offsets_by_start = {start: smd_candidate_offsets(header, start) for start in starts}
    if state is None:
        state = {start: {"prefecture": None, "district_number": None} for start in starts}
    else:
        for start in starts:
            state.setdefault(start, {"prefecture": None, "district_number": None})

    for row_index, row in rows:
        for start in starts:
            offsets = offsets_by_start[start]
            label = compact(row[start] if start < len(row) else None)
            district = re.fullmatch(r"(.+?[都道府県])第(\d+)区", label)
            if district:
                state[start]["prefecture"] = district.group(1)
                state[start]["district_number"] = int(district.group(2))
                continue
            if label not in {"当", "落"} or state[start]["prefecture"] is None:
                continue

            def cell(offset: int | None) -> Any:
                if offset is None:
                    return None
                index = start + offset
                return row[index] if index < len(row) else None

            name_offset = offsets["name"]
            if name_lookup is not None and name_offset is not None:
                name, raw_name = name_lookup(row_index, start, name_offset, cell(name_offset))
            else:
                name, raw_name = candidate_name(cell(name_offset))
            votes = number(cell(offsets["votes"]))
            if not name or votes is None:
                continue
            gender_value = compact(cell(offsets["gender"])) if offsets["gender"] is not None else ""
            fact = make_fact(row_index=row_index, start=start)
            fact.update({
                "contest": "smd",
                "prefecture": state[start]["prefecture"],
                "district_number": state[start]["district_number"],
                "candidate": name,
                "candidate_raw": raw_name,
                "gender": gender_value or None,
                "age": number(cell(offsets["age"])),
                "party": compact(cell(offsets["party"])),
                "candidate_status": status_map.get(compact(cell(offsets["status"]))),
                "occupation": compact(cell(offsets["occupation"])),
                "elected": label == "当",
                "dual_candidacy": compact(cell(offsets["dual"])) == "重",
                "sekihairitsu": number(cell(offsets["sekihairitsu"])),
                "metric": "candidate_votes",
                "value": votes,
                "unit": "votes",
            })
            output.append(fact)
    return output, state


def parse_pdf_smd_candidates(doc: dict[str, Any], pdf_path: Path) -> list[dict[str, Any]]:
    """Parse 03-13 SMD candidate vote PDFs for both gender and no-gender layouts.

    Uses a single reading-order state across panels/pages (same approach as the
    original validator-passing importer), with header-driven column offsets.
    """
    output: list[dict[str, Any]] = []
    status_map = {"新": "new", "前": "incumbent", "元": "former"}
    prefecture = None
    district_number = None
    with pdfplumber.open(pdf_path) as pdf:
        for page_index, page in enumerate(pdf.pages, 1):
            tables = page.extract_tables()
            if not tables or not tables[0]:
                continue
            table = tables[0]
            header = table[0]
            starts = smd_candidate_panel_starts(header) or [0]
            offsets_by_start = {start: smd_candidate_offsets(header, start) for start in starts}
            for start in starts:
                offsets = offsets_by_start[start]
                for row_index, row in enumerate(table[1:], 2):
                    label = compact(row[start] if start < len(row) else None)
                    district = re.fullmatch(r"(.+?[都道府県])第(\d+)区", label)
                    if district:
                        prefecture, district_number = district.group(1), int(district.group(2))
                        continue
                    if label not in {"当", "落"} or prefecture is None:
                        continue

                    def cell(offset: int | None, _row=row, _start=start) -> Any:
                        if offset is None:
                            return None
                        index = _start + offset
                        return _row[index] if index < len(_row) else None

                    name, raw_name = candidate_name(cell(offsets["name"]))
                    votes = number(cell(offsets["votes"]))
                    if not name or votes is None:
                        continue
                    gender_value = compact(cell(offsets["gender"])) if offsets["gender"] is not None else ""
                    fact = pdf_fact_base(doc, page_index, f"table:R{row_index}C{start + 1}")
                    fact.update({
                        "contest": "smd",
                        "prefecture": prefecture,
                        "district_number": district_number,
                        "candidate": name,
                        "candidate_raw": raw_name,
                        "gender": gender_value or None,
                        "age": number(cell(offsets["age"])),
                        "party": compact(cell(offsets["party"])),
                        "candidate_status": status_map.get(compact(cell(offsets["status"]))),
                        "occupation": compact(cell(offsets["occupation"])),
                        "elected": label == "当",
                        "dual_candidacy": compact(cell(offsets["dual"])) == "重",
                        "sekihairitsu": number(cell(offsets["sekihairitsu"])),
                        "metric": "candidate_votes",
                        "value": votes,
                        "unit": "votes",
                    })
                    output.append(fact)
    return output


def parse_xls_smd_candidates(doc: dict[str, Any], sheet: dict[str, Any], table: list[list[Any]]) -> list[dict[str, Any]]:
    """Parse 03-13 SMD candidate vote Excel workbooks.

    MIC Excel dumps keep the printed two-column page layout. Notes rows mark page
    boundaries; within each page we read left panel then right panel (zigzag),
    matching the PDF importer that passes prefecture vote validation.
    """
    if not table:
        return []
    header_index = next((index for index, row in enumerate(table)
                         if sum(compact(value) == "当落" for value in row) >= 1), None)
    if header_index is None:
        return []
    header = list(table[header_index])
    if header_index + 1 < len(table):
        for column, value in enumerate(table[header_index + 1]):
            if compact(value) and column < len(header):
                header[column] = f"{header[column] or ''}{value or ''}"

    starts = smd_candidate_panel_starts(header) or [0]
    offsets_by_start = {start: smd_candidate_offsets(header, start) for start in starts}
    status_map = {"新": "new", "前": "incumbent", "元": "former"}

    bounds = [header_index + 2]
    for row_index, row in enumerate(table[header_index + 2 :], header_index + 2):
        text = str(row[0] if row else "")
        if text.startswith("(注)") or text.startswith("（注）"):
            bounds.append(row_index)
    bounds.append(len(table))

    segments: list[tuple[int, int]] = []
    for index in range(len(bounds) - 1):
        start_row, end_row = bounds[index], bounds[index + 1]
        text = str(table[start_row][0] if start_row < len(table) and table[start_row] else "")
        if text.startswith("(注)") or text.startswith("（注）"):
            cursor = start_row
            while cursor < end_row:
                row = table[cursor]
                cell0 = str(row[0] if row else "")
                if cell0.startswith("(注)") or cell0.startswith("（注）") or cell0.startswith(" "):
                    cursor += 1
                    continue
                if not any(compact(value) for value in row[:12]):
                    cursor += 1
                    continue
                break
            start_row = cursor
        if start_row < end_row:
            segments.append((start_row, end_row))

    output: list[dict[str, Any]] = []
    prefecture = None
    district_number = None
    for seg_start, seg_end in segments:
        for start in starts:
            offsets = offsets_by_start[start]
            for row_index in range(seg_start, seg_end):
                row = table[row_index]
                label = compact(row[start] if start < len(row) else None)
                district = re.fullmatch(r"(.+?[都道府県])第(\d+)区", label)
                if district:
                    prefecture, district_number = district.group(1), int(district.group(2))
                    continue
                if label not in {"当", "落"} or prefecture is None:
                    continue

                def cell(offset: int | None, _row=row, _start=start) -> Any:
                    if offset is None:
                        return None
                    index = _start + offset
                    return _row[index] if index < len(_row) else None

                chunks = [str(cell(offsets["name"]) or "")]
                name_col = start + (offsets["name"] or 0)
                for look in (1, 2):
                    peek_idx = row_index + look
                    if peek_idx >= len(table) or name_col >= len(table[peek_idx]):
                        break
                    text = str(table[peek_idx][name_col] or "")
                    if "(" in text or "（" in text:
                        chunks.append(text)
                        break
                name, raw_name = candidate_name("\n".join(chunks))
                votes = number(cell(offsets["votes"]))
                if not name or votes is None:
                    continue
                gender_value = compact(cell(offsets["gender"])) if offsets["gender"] is not None else ""
                fact = base(doc, sheet, row_index + 1, start)
                fact.update({
                    "contest": "smd",
                    "prefecture": prefecture,
                    "district_number": district_number,
                    "candidate": name,
                    "candidate_raw": raw_name,
                    "gender": gender_value or None,
                    "age": number(cell(offsets["age"])),
                    "party": compact(cell(offsets["party"])),
                    "candidate_status": status_map.get(compact(cell(offsets["status"]))),
                    "occupation": compact(cell(offsets["occupation"])),
                    "elected": label == "当",
                    "dual_candidacy": compact(cell(offsets["dual"])) == "重",
                    "sekihairitsu": number(cell(offsets["sekihairitsu"])),
                    "metric": "candidate_votes",
                    "value": votes,
                    "unit": "votes",
                })
                output.append(fact)
    return output


def _lines(value: Any) -> list[str]:
    return [line.strip() for line in str(value or "").splitlines() if str(line).strip()]


def parse_xls_pr_elected(doc: dict[str, Any], sheet: dict[str, Any], table: list[list[Any]]) -> list[dict[str, Any]]:
    """Normalize 03-11 Excel panels (party votes / elected counts / list ranks)."""
    output: list[dict[str, Any]] = []
    header_rows = [
        index for index, row in enumerate(table)
        if any(compact(value) in {"政党等名", "党派名"} for value in row)
    ]
    block_at: dict[int, str] = {}
    current_block = ""
    for row_index, row in enumerate(table):
        label0 = compact(row[0] if row else None)
        if "選挙区" in label0:
            current_block = compact(label0.replace("選挙区", ""))
        block_at[row_index] = current_block

    for header_pos, row_index in enumerate(header_rows):
        row = table[row_index]
        block = block_at.get(row_index, "")
        end = header_rows[header_pos + 1] if header_pos + 1 < len(header_rows) else len(table)
        starts = [index for index, value in enumerate(row) if compact(value) in {"政党等名", "党派名"}]
        for start in starts:
            party = compact(row[start + 2] if start + 2 < len(row) else None)
            if not party:
                continue
            votes = clean_count(table[row_index + 2][start + 2] if row_index + 2 < len(table) else None)
            elected_total = clean_count(table[row_index + 3][start + 2] if row_index + 3 < len(table) else None)
            gender_row = table[row_index + 4] if row_index + 4 < len(table) else []
            counts = {
                "total": elected_total,
                "male": clean_count(gender_row[start + 1] if start + 1 < len(gender_row) else None),
                "female": clean_count(gender_row[start + 4] if start + 4 < len(gender_row) else None),
            }
            if votes is not None:
                fact = base(doc, sheet, row_index + 2, start + 2)
                fact.update({"contest": "pr", "pr_block": block, "party": party,
                             "metric": "party_votes", "value": votes, "unit": "votes"})
                output.append(fact)
            if (
                all(value is not None for value in counts.values())
                and counts["male"] + counts["female"] == counts["total"]
            ):
                for gender, value in counts.items():
                    col = start + 2 if gender == "total" else start + 1 if gender == "male" else start + 4
                    fact = base(doc, sheet, row_index + (4 if gender != "total" else 3), col)
                    fact.update({"contest": "pr", "pr_block": block, "party": party,
                                 "gender": gender, "metric": "elected_candidates",
                                 "value": value, "unit": "people"})
                    output.append(fact)
            for list_index in range(row_index + 6, end):
                list_row = table[list_index]
                label0 = compact(list_row[0] if list_row else None)
                if "選挙区" in label0:
                    break
                position = number(list_row[start] if start < len(list_row) else None)
                name_raw = str(list_row[start + 1] if start + 1 < len(list_row) else "" or "")
                name = compact(name_raw)
                if position is None or not name:
                    continue
                fact = base(doc, sheet, list_index, start + 1)
                fact.update({"contest": "pr", "pr_block": block, "party": party,
                             "candidate": name, "candidate_raw": name_raw.strip(),
                             "metric": "pr_list_position", "value": position, "unit": "rank"})
                output.append(fact)
    return output


def parse_age_turnout_1819(doc: dict[str, Any], sheet: dict[str, Any], table: list[list[Any]]) -> list[dict[str, Any]]:
    """Normalize 03-15 prefecture × 18/19 voting workbook."""
    output: list[dict[str, Any]] = []
    for row_index, row in enumerate(table):
        prefecture = compact(row[1] if len(row) > 1 else None)
        if not prefecture or prefecture in {"都道府県", "都道"}:
            continue
        if not (PREFECTURE.search(prefecture) or prefecture in {"全国", "計", "合計"}):
            continue
        # columns: 3-5 eligible 18/19/total, 6-8 voters, 9-11 turnout, 12 overall turnout
        specs = [
            (3, "18", "eligible_voters", "people"),
            (4, "19", "eligible_voters", "people"),
            (5, "18-19", "eligible_voters", "people"),
            (6, "18", "voters", "people"),
            (7, "19", "voters", "people"),
            (8, "18-19", "voters", "people"),
            (9, "18", "turnout_rate", "percent"),
            (10, "19", "turnout_rate", "percent"),
            (11, "18-19", "turnout_rate", "percent"),
            (12, "all", "turnout_rate", "percent"),
        ]
        for column, age_band, metric, unit in specs:
            value = number(row[column] if column < len(row) else None)
            if value is None:
                continue
            fact = base(doc, sheet, row_index, column)
            fact.update({
                "contest": "all",
                "prefecture": prefecture,
                "age_band": age_band,
                "gender": "total" if age_band != "all" else "total",
                "metric": metric,
                "value": value,
                "unit": unit,
                "row_variant": "age_18_19" if age_band != "all" else "overall_reference",
            })
            output.append(fact)
    return output


def parse_age_turnout_by_age(doc: dict[str, Any], sheet: dict[str, Any], table: list[list[Any]]) -> list[dict[str, Any]]:
    """Normalize 03-16 Excel: national sample by single-year age and gender."""
    output: list[dict[str, Any]] = []
    for row_index, row in enumerate(table):
        age_label = compact(row[0] if row else None)
        if not age_label or age_label in {"年齢", "年齢（歳）"}:
            continue
        if age_label == "小計":
            age_band = "subtotal"
        elif age_label in {"計", "合計"}:
            age_band = "total"
        else:
            age_band = age_label.replace("歳以上", "+").replace("歳", "")
        genders = ("male", "female", "total")
        for metric, offset, unit in (
            ("eligible_voters", 1, "people"),
            ("voters", 4, "people"),
            ("turnout_rate", 7, "percent"),
        ):
            for gender_index, gender in enumerate(genders):
                column = offset + gender_index
                value = number(row[column] if column < len(row) else None)
                if value is None:
                    continue
                fact = base(doc, sheet, row_index, column)
                fact.update({
                    "contest": "all",
                    "prefecture": "全国",
                    "age_band": age_band,
                    "gender": gender,
                    "metric": metric,
                    "value": value,
                    "unit": unit,
                    "row_variant": "age_sample",
                })
                output.append(fact)
    return output


def parse_pdf_age_turnout_table(
    doc: dict[str, Any],
    page_index: int,
    table: list[list[Any]],
    source_file: str,
) -> list[dict[str, Any]]:
    """Parse 付表１/付表２ style age turnout tables (often one multiline data row)."""
    if not table or len(table) < 3:
        return []
    # locate gender header
    header_index = next(
        (index for index, row in enumerate(table[:5]) if sum(1 for v in row if compact(v) == "男") >= 2),
        1,
    )
    data_rows = table[header_index + 1 :]
    output: list[dict[str, Any]] = []

    def emit(age_label: str, values: list[Any], cell_tag: str) -> None:
        label = compact(age_label)
        if not label:
            return
        if label in {"計", "合計"}:
            age_band, variant = "total", "sample_total"
        elif "全国" in label:
            age_band, variant = "total", "national_total"
        else:
            age_band = label.replace("歳以上", "+").replace("歳", "").replace("～", "-").replace("~", "-")
            variant = "age_band_sample" if "-" in age_band or "～" in label else "age_sample"
        # expected: 9 or 12 numeric columns after age (elig m/f/t, voters m/f/t, rate m/f/t[, prev...])
        nums = [number(v) for v in values]
        specs = [
            (0, "eligible_voters", "people", "male"),
            (1, "eligible_voters", "people", "female"),
            (2, "eligible_voters", "people", "total"),
            (3, "voters", "people", "male"),
            (4, "voters", "people", "female"),
            (5, "voters", "people", "total"),
            (6, "turnout_rate", "percent", "male"),
            (7, "turnout_rate", "percent", "female"),
            (8, "turnout_rate", "percent", "total"),
        ]
        for offset, metric, unit, gender in specs:
            if offset >= len(nums) or nums[offset] is None:
                continue
            fact = {
                "election_kaiji": doc["election_kaiji"],
                "source_code": doc["source_code"],
                "dataset": doc.get("dataset"),
                "source_url": doc.get("source_url"),
                "source_file": source_file,
                "source_sheet": f"page {page_index}",
                "source_cell": cell_tag,
                "contest": "all",
                "prefecture": "全国",
                "age_band": age_band,
                "gender": gender,
                "metric": metric,
                "value": nums[offset],
                "unit": unit,
                "row_variant": variant,
            }
            output.append(fact)

    for row_index, row in enumerate(data_rows):
        age_cell = row[0] if row else None
        ages = _lines(age_cell)
        if len(ages) <= 1:
            # ordinary single-age row
            emit(str(age_cell or ""), row[1:10], f"table:R{header_index + 1 + row_index}")
            continue
        # multiline packed row
        col_lines = [_lines(row[col]) if col < len(row) else [] for col in range(1, 10)]
        for age_index, age_label in enumerate(ages):
            values = [col[age_index] if age_index < len(col) else None for col in col_lines]
            emit(age_label, values, f"table:multiline:{age_index + 1}")
    return output


def parse_pdf_age_turnout(doc: dict[str, Any], pdf_path: Path) -> list[dict[str, Any]]:
    """Normalize 03-16 PDF body and/or extracted portfolio attachments."""
    output: list[dict[str, Any]] = []
    candidates: list[Path] = [pdf_path]
    attachments_dir = pdf_path.parent / f"{pdf_path.stem}_attachments"
    if attachments_dir.exists():
        candidates.extend(sorted(attachments_dir.glob("*.pdf")))
    for path in candidates:
        name = path.name
        # skip overview-only cover pages without 付表
        with pdfplumber.open(path) as pdf:
            for page_index, page in enumerate(pdf.pages, 1):
                text = page.extract_text() or ""
                if "年齢別投票者数" not in text and "年齢階層別" not in text:
                    continue
                # Prefer national tables; skip municipality detail pages of 付表２
                if "市区町村" in text and "１．全国" not in text and "1．全国" not in text and "１.全国" not in text:
                    # page may still start with national; allow if 全国 section marker exists earlier
                    if not re.search(r"[１1][\.．]\s*全国", text):
                        continue
                tables = page.extract_tables() or []
                if not tables:
                    continue
                output.extend(parse_pdf_age_turnout_table(doc, page_index, tables[0], name))
                # 付表２ may have national table as first table only
    return output


def parse_pdf_remaining(doc: dict[str, Any], pdf_path: Path) -> list[dict[str, Any]]:
    return {"03-10": parse_pdf_pr_ranking, "03-11": parse_pdf_pr_elected,
            "03-12": parse_pdf_seat_allocation, "03-13": parse_pdf_smd_candidates}[doc["source_code"]](doc, pdf_path)


PARSERS = {
    "01-01": parse_party_status_gender,
    "01-02": parse_prefecture_party_status,
    "01-03": parse_ages,
    "02-01": parse_people,
    "02-01-02": parse_rates,
    "02-02": parse_people,
    "02-02-02": parse_rates,
    "03-01": parse_party_status_gender,
    "03-02": parse_prefecture_party_status,
    "03-03": parse_ages,
    "03-04": parse_party_comparison,
    "03-05": parse_party_comparison,
    "03-06": parse_prefecture_party_gender,
    "03-07": parse_pr_prefecture_party,
    "03-08": parse_ballots,
    "03-09": parse_ballots,
    "03-10": parse_pr_block_ranking,
    "03-11": parse_xls_pr_elected,
    "03-12": parse_seat_allocation,
    "03-13": parse_xls_smd_candidates,
    "03-15": parse_age_turnout_1819,
    "03-16": parse_age_turnout_by_age,
    "05-01": parse_people,
    "05-01-02": parse_rates,
    "05-02": parse_judicial_votes_v2,
    "05-03": parse_ballots,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="raw JSONから分析用選挙factを作成")
    parser.add_argument("--input", type=Path, required=True, help="raw_jsonディレクトリ")
    parser.add_argument("--output", type=Path, required=True, help="normalized出力ディレクトリ")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    facts: list[dict[str, Any]] = []
    coverage: list[dict[str, Any]] = []
    for path in sorted(args.input.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        code = doc.get("source_code") or path.name.split("_", 1)[0]
        doc["source_code"] = code
        selected = PARSERS.get(code)
        before = len(facts)
        if selected and "sheets" in doc:
            for sheet in doc["sheets"]:
                facts.extend(selected(doc, sheet, matrix(doc, sheet)))
        elif code in PDF_PARTY_STATUS_CODES and "pages" in doc:
            pdf_path = args.input.parent / "raw" / doc["source_file"]
            if pdf_path.exists():
                facts.extend(parse_pdf_party_status(doc, pdf_path))
        elif code in PDF_PARTY_COMPARISON_CODES and "pages" in doc:
            pdf_path = args.input.parent / "raw" / doc["source_file"]
            if pdf_path.exists():
                facts.extend(parse_pdf_party_comparison(doc, pdf_path))
        elif code in PDF_GEOMETRIC_CODES and "pages" in doc:
            pdf_path = args.input.parent / "raw" / doc["source_file"]
            if pdf_path.exists():
                facts.extend(parse_pdf_geometric(doc, pdf_path))
        elif code in PDF_REMAINING_CODES and "pages" in doc:
            pdf_path = args.input.parent / "raw" / doc["source_file"]
            if pdf_path.exists():
                facts.extend(parse_pdf_remaining(doc, pdf_path))
        elif code == "03-16" and "pages" in doc:
            pdf_path = args.input.parent / "raw" / doc["source_file"]
            if pdf_path.exists():
                facts.extend(parse_pdf_age_turnout(doc, pdf_path))
        elif code in PDF_SUMMARY_CODES and "pages" in doc:
            pdf_path = args.input.parent / "raw" / doc["source_file"]
            if pdf_path.exists():
                facts.extend(parse_pdf_summary(doc, pdf_path))
        elif code == "05-02" and "pages" in doc:
            facts.extend(parse_pdf_judicial_votes(doc))
        produced = len(facts) - before
        coverage.append({
            "source_code": code,
            "dataset": doc.get("dataset"),
            "status": "normalized" if produced else "raw_only",
            "records": produced,
        })
    (args.output / "facts.json").write_text(json.dumps(facts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    candidate_metrics = {"candidates", "elected_candidates"}
    domains = {
        "candidate_facts.json": [item for item in facts if item["metric"] in candidate_metrics],
        "candidate_vote_facts.json": [item for item in facts if item["metric"] == "candidate_votes"],
        "party_facts.json": [item for item in facts if item.get("party") is not None],
        "turnout_facts.json": [item for item in facts if item["metric"] not in candidate_metrics and item.get("party") is None and item.get("contest") != "judicial_review"],
        "judicial_review_facts.json": [item for item in facts if item.get("contest") == "judicial_review"],
    }
    for filename, records in domains.items():
        (args.output / filename).write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": "1.0",
        "records": len(facts),
        "normalized_sources": sum(item["status"] == "normalized" for item in coverage),
        "domain_records": {filename: len(records) for filename, records in domains.items()},
        "coverage": coverage,
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"records": len(facts), "normalized_sources": manifest["normalized_sources"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
