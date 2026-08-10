# v1.3.2: 03-13 左右パネルで県ヘッダを他パネルへコピーしない（隣県への誤帰属を防止）
# v1.3.1: 03-13 旧Excel（当/落分割ヘッダ・性別列あり）に対応
# v1.3.0: unclassified（03-11相当）都道府県×名簿候補者得票を追加
# v1.2.0: 03-13 県区の定数（1人区等）を district_number に保存
# v1.1.0: 03-05比例都道府県党派、03-09順位、03-10名簿、03-13選挙区候補者を追加
# v1.0.0: 参院（sangiin）専用正規化パーサ。衆院 PARSERS とは項番の意味が衝突するため分離。
"""House of Councillors (sangiin) semantic parsers."""
from __future__ import annotations

import re
from typing import Any

# Reuse helpers from normalize without circular import at module load:
# callers pass already-imported callables / we import inside functions.

# 例: 北海道(定数3名) / 東京都(定数6(1)名) / 鳥取県・島根県(定数1名)
_PREF_HEADER = re.compile(r"^(.+?)\(定数(\d+)(?:\((\d+)\))?名\)")
_STATUS_MAP = {"新": "new", "現": "incumbent", "前": "incumbent", "元": "former"}


def _attach_chamber(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for fact in facts:
        fact["chamber"] = "sangiin"
        fact.setdefault("election_type", "sangiin")
    return facts


def parse_sangiin_people(doc: dict[str, Any], sheet: dict[str, Any], table: list[list[Any]]) -> list[dict[str, Any]]:
    """02-01=比例, 02-02=選挙区. いずれも都道府県×男女の人数表（ブロック列なし）."""
    from soumu_election.normalize import base, compact, number, prefecture_rows

    code = doc.get("source_code", "")
    contest = "pr" if code.startswith("02-01") else "district" if code.startswith("02-02") else None
    if contest is None:
        return []
    metrics = ("eligible_voters", "voters", "abstentions")
    genders = ("male", "female", "total")
    output = []
    for row_index, prefecture in prefecture_rows(table, 0):
        row = table[row_index]
        for metric_index, metric in enumerate(metrics):
            for gender_index, gender in enumerate(genders):
                column = 1 + metric_index * 3 + gender_index
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
                output.append(fact)
    return _attach_chamber(output)


def parse_sangiin_rates(doc: dict[str, Any], sheet: dict[str, Any], table: list[list[Any]]) -> list[dict[str, Any]]:
    """02-01-cmp=比例投票率, 02-02-cmp=選挙区投票率."""
    from soumu_election.normalize import base, number, prefecture_rows

    code = doc.get("source_code", "")
    contest = "pr" if code.startswith("02-01") else "district" if code.startswith("02-02") else None
    if contest is None:
        return []
    metrics = ("turnout_rate", "previous_turnout_rate", "turnout_rate_change")
    genders = ("male", "female", "total")
    output = []
    for row_index, prefecture in prefecture_rows(table, 0):
        row = table[row_index]
        for metric_index, metric in enumerate(metrics):
            for gender_index, gender in enumerate(genders):
                column = 1 + metric_index * 3 + gender_index
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
                output.append(fact)
    return _attach_chamber(output)


def parse_sangiin_ballots(doc: dict[str, Any], sheet: dict[str, Any], table: list[list[Any]]) -> list[dict[str, Any]]:
    """03-07=比例票数, 03-08=選挙区票数."""
    from soumu_election.normalize import base, compact, number, prefecture_rows

    code = doc.get("source_code", "")
    contest = "pr" if code == "03-07" else "district" if code == "03-08" else None
    if contest is None:
        return []
    header_row = next((row for row in table[:8] if any(compact(v) in {"区分", "都道府県"} for v in row)), [])
    pref_column = next((i for i, value in enumerate(header_row) if compact(value) in {"区分", "都道府県"}), 0)
    metrics = ("ballots_cast", "valid_ballots", "invalid_ballots", "invalid_ballot_rate")
    output = []
    for row_index, prefecture in prefecture_rows(table, pref_column):
        row = table[row_index]
        for offset, metric in enumerate(metrics):
            column = pref_column + 1 + offset
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
            output.append(fact)
    return _attach_chamber(output)


def parse_sangiin_party_comparison(doc: dict[str, Any], sheet: dict[str, Any], table: list[list[Any]]) -> list[dict[str, Any]]:
    """03-03=比例全国党派得票, 03-04=選挙区全国党派得票."""
    from soumu_election.normalize import base, compact, number

    code = doc.get("source_code", "")
    contest = "pr" if code == "03-03" else "district" if code == "03-04" else None
    if contest is None:
        return []
    # 衆院 parse_party_comparison と同型（区分ヘッダ＋今回/前回…）
    row_metrics = {
        2: ("current_votes", "votes"),
        4: ("current_vote_share", "ratio"),
        5: ("previous_votes", "votes"),
        7: ("previous_vote_share", "ratio"),
        8: ("vote_change", "votes"),
        10: ("vote_change_rate", "ratio"),
    }
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
                fact.update({
                    "contest": contest,
                    "party": party,
                    "metric": metric,
                    "value": value,
                    "unit": unit,
                })
                output.append(fact)
    return _attach_chamber(output)


def parse_sangiin_prefecture_party_gender(doc: dict[str, Any], sheet: dict[str, Any], table: list[list[Any]]) -> list[dict[str, Any]]:
    """03-06 都道府県別党派別得票（選挙区・男女計）."""
    from soumu_election.normalize import base, compact, number, party_headers, prefecture_rows

    header_index = next((i for i, row in enumerate(table) if len(party_headers(row, 1, 3)) >= 2), None)
    if header_index is None:
        return []
    parties = party_headers(table[header_index], 1, 3)
    gender_index = next(
        (i for i in range(header_index + 1, min(header_index + 5, len(table))) if compact(table[i][1]) == "男"),
        None,
    )
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
                fact.update({
                    "contest": "district",
                    "prefecture": prefecture,
                    "party": party,
                    "gender": gender,
                    "metric": "party_votes",
                    "value": value,
                    "unit": "votes",
                })
                output.append(fact)
    return _attach_chamber(output)


def parse_sangiin_pr_prefecture_party(doc: dict[str, Any], sheet: dict[str, Any], table: list[list[Any]]) -> list[dict[str, Any]]:
    """03-05 都道府県別党派別得票（比例）。4党×4列ブロックが縦に続く。"""
    from soumu_election.normalize import PREFECTURE, base, compact, number

    output: list[dict[str, Any]] = []
    parties: list[tuple[int, str]] = []
    for row_index, row in enumerate(table):
        label0 = compact(row[0] if row else None)
        # 党派ヘッダ行（列1,5,9,13…）
        header_parties = [
            (c, compact(v))
            for c, v in enumerate(row)
            if c % 4 == 1 and compact(v) and compact(v) not in {"得票総数", "都道府県"}
        ]
        if label0 in {"", "政党等の名称"} and len(header_parties) >= 1 and all(
            p and p not in {"得票総数", "政党等の", "名簿登載者（特定枠"} for _, p in header_parties
        ):
            # 合計ブロックはスキップ
            if any(p == "合計" for _, p in header_parties):
                parties = []
                continue
            if any("党" in p or p in {"諸派", "無所属", "チームみらい", "再生の道", "無所属連合", "日本改革党", "日本誠真会", "ＮＨＫ党", "れいわ新選組", "参政党"} for _, p in header_parties):
                parties = header_parties
                continue

        if not parties:
            continue
        prefecture = label0
        if not (PREFECTURE.search(prefecture) or prefecture in {"計", "合計", "全国"}):
            continue
        for start, party in parties:
            if party == "合計":
                continue
            metrics = (
                (0, "party_votes", "votes"),
                (1, "party_vote_share", "percent"),
                (2, "party_only_votes", "votes"),
                (3, "list_candidate_votes", "votes"),
            )
            for offset, metric, unit in metrics:
                column = start + offset
                value = number(row[column] if column < len(row) else None)
                if value is None:
                    continue
                fact = base(doc, sheet, row_index, column)
                fact.update({
                    "contest": "pr",
                    "prefecture": prefecture,
                    "party": party,
                    "metric": metric,
                    "value": value,
                    "unit": unit,
                })
                output.append(fact)
    return _attach_chamber(output)


def parse_sangiin_pr_ranking(doc: dict[str, Any], sheet: dict[str, Any], table: list[list[Any]]) -> list[dict[str, Any]]:
    """03-09 得票順党派別得票数（比例・全国）。3列パネル×複数。"""
    from soumu_election.normalize import base, compact, number

    output: list[dict[str, Any]] = []
    starts = [0, 4, 8]
    for row_index, row in enumerate(table):
        for start in starts:
            rank = number(row[start] if start < len(row) else None)
            party = compact(row[start + 1] if start + 1 < len(row) else None)
            votes = number(row[start + 2] if start + 2 < len(row) else None)
            share = number(row[start + 3] if start + 3 < len(row) else None)
            if rank is None or not party or party in {"党派名", "得票総数", "順位"}:
                continue
            for column, metric, value, unit in (
                (start, "party_rank", rank, "rank"),
                (start + 2, "party_votes", votes, "votes"),
                (start + 3, "party_vote_share", share, "percent"),
            ):
                if value is None:
                    continue
                fact = base(doc, sheet, row_index, column)
                fact.update({
                    "contest": "pr",
                    "party": party,
                    "metric": metric,
                    "value": value,
                    "unit": unit,
                })
                output.append(fact)
    return _attach_chamber(output)


def parse_sangiin_pr_list_candidates(doc: dict[str, Any], sheet: dict[str, Any], table: list[list[Any]]) -> list[dict[str, Any]]:
    """03-10 党派別名簿登載者別得票・当選（比例・全国）。6列パネル。"""
    from soumu_election.normalize import base, candidate_name, compact, number

    def looks_like_party(name: str) -> bool:
        if not name or name.replace(".", "", 1).isdigit():
            return False
        if name in {"男", "女", "計", "順位", "当落", "得票数", "得票総数", "合計"}:
            return False
        if "得票" in name or "当選" in name or "名簿" in name:
            return False
        return True

    output: list[dict[str, Any]] = []
    parties_by_start: dict[int, str] = {}
    panel_width = 6
    starts = list(range(0, 24, panel_width))

    for row_index, row in enumerate(table):
        if any(compact(row[s] if s < len(row) else None) == "政党等の名称" for s in starts):
            parties_by_start = {}
            for look in range(1, 4):
                peek = row_index + look
                if peek >= len(table):
                    break
                prow = table[peek]
                found = False
                for start in starts:
                    party = compact(prow[start + 3] if start + 3 < len(prow) else None)
                    if looks_like_party(party):
                        parties_by_start[start] = party
                        found = True
                if found:
                    break
            continue

        for start, party in list(parties_by_start.items()):
            rank = number(row[start] if start < len(row) else None)
            elected_mark = compact(row[start + 1] if start + 1 < len(row) else None)
            name_cell = row[start + 2] if start + 2 < len(row) else None
            # 当落が空の名簿行もある（小党など）
            if elected_mark not in {"当", "落", ""}:
                continue
            if rank is None or rank < 1:
                continue
            chunks = [str(name_cell or "")]
            for look in (1, 2):
                peek = row_index + look
                if peek >= len(table):
                    break
                text = str(table[peek][start + 2] if start + 2 < len(table[peek]) else "")
                if "(" in text or "（" in text:
                    chunks.append(text)
                    break
            name, raw_name = candidate_name("\n".join(chunks))
            if not name or name in {"名簿登載者名", "得票数"}:
                continue
            votes = number(row[start + 4] if start + 4 < len(row) else None)
            if votes is None:
                votes = number(row[start + 5] if start + 5 < len(row) else None)
            fact = base(doc, sheet, row_index, start)
            fact.update({
                "contest": "pr",
                "party": party,
                "candidate": name,
                "candidate_raw": raw_name,
                "elected": elected_mark == "当",
                "allocation_rank": rank,
                "metric": "candidate_votes",
                "value": votes if votes is not None else 0,
                "unit": "votes",
            })
            if votes is None:
                fact["row_variant"] = "no_personal_votes"
            if elected_mark == "":
                fact["row_variant"] = (fact.get("row_variant") or "") + "|no_elected_mark"
            output.append(fact)
    return _attach_chamber(output)


def parse_sangiin_district_candidates(doc: dict[str, Any], sheet: dict[str, Any], table: list[list[Any]]) -> list[dict[str, Any]]:
    """03-13 候補者別得票数（県区）。左右独立パネル。定数は district_number に格納（1人区=1）。

    対応レイアウト:
    - 新: ヘッダ「当落」＋（氏名/年齢/党派/新現/職業/得票）
    - 旧: ヘッダ「当」＋次行「落」、性別列あり（氏名/性別/年齢/党派/新現/職業/得票）
    """
    from soumu_election.normalize import base, candidate_name, compact, number

    if not table:
        return []

    header_index = None
    for i, row in enumerate(table):
        if sum(compact(v) == "当落" for v in row) >= 1:
            header_index = i
            break
        if i + 1 >= len(table):
            continue
        nxt = table[i + 1]
        split_hits = 0
        for col, value in enumerate(row):
            if compact(value) != "当":
                continue
            if compact(nxt[col] if col < len(nxt) else None) == "落":
                split_hits += 1
        if split_hits >= 1:
            header_index = i
            break
    if header_index is None:
        return []

    header = table[header_index]
    starts = [i for i, v in enumerate(header) if compact(v) in {"当落", "当"}] or [0, 7]
    has_gender = any(compact(v) == "性別" for v in header)
    if has_gender:
        field_offsets = {
            "name": 1, "gender": 2, "age": 3, "party": 4, "status": 5, "occupation": 6, "votes": 7,
        }
    else:
        field_offsets = {
            "name": 1, "age": 2, "party": 3, "status": 4, "occupation": 5, "votes": 6,
        }

    # panel -> (prefecture, seats, byelection_seats|None)
    district_by_panel: dict[int, tuple[str, int, int | None]] = {}
    output: list[dict[str, Any]] = []

    def set_district(start: int, prefecture: str, seats: int, byelection: int | None) -> None:
        # パネルごとに独立。他パネルへコピーすると次県の候補が前県に付く（参27で確認）
        district_by_panel[start] = (prefecture, seats, byelection)

    for row_index in range(header_index + 1, len(table)):
        row = table[row_index]
        for start in starts:
            for probe_col in (start, start + 1):
                text = compact(row[probe_col] if probe_col < len(row) else None)
                matched = _PREF_HEADER.match(text) if text else None
                if not matched:
                    continue
                prefecture = matched.group(1)
                if not ("都" in prefecture or "道" in prefecture or "府" in prefecture or "県" in prefecture):
                    continue
                seats = int(matched.group(2))
                byelection = int(matched.group(3)) if matched.group(3) else None
                set_district(start, prefecture, seats, byelection)
                break

            label = compact(row[start] if start < len(row) else None)
            if label not in {"当", "落"}:
                continue
            current = district_by_panel.get(start)
            if not current:
                continue
            prefecture, seats, byelection = current

            name_col = start + field_offsets["name"]
            chunks = [str(row[name_col] if name_col < len(row) else "")]
            if row_index > 0 and name_col < len(table[row_index - 1]):
                prev = str(table[row_index - 1][name_col] or "")
                prev_c = compact(prev)
                if prev and "(" not in prev and "（" not in prev and prev_c not in {"当", "落"}:
                    if not re.search(r"[0-9]", prev) and not _PREF_HEADER.match(prev_c):
                        chunks.insert(0, prev)
            for look in (1, 2):
                peek = row_index + look
                if peek >= len(table) or name_col >= len(table[peek]):
                    break
                text = str(table[peek][name_col] or "")
                if "(" in text or "（" in text:
                    chunks.append(text)
                    break
            name, raw_name = candidate_name("\n".join(chunks))
            votes = number(row[start + field_offsets["votes"]] if start + field_offsets["votes"] < len(row) else None)
            if not name or votes is None:
                continue
            status = compact(row[start + field_offsets["status"]] if start + field_offsets["status"] < len(row) else None)
            fact = base(doc, sheet, row_index, start)
            fact.update({
                "contest": "district",
                "prefecture": prefecture,
                # 参院県区の定数（1人区=1, 3人区=3）。衆院の「第N区」とは意味が異なる。
                "district_number": seats,
                "candidate": name,
                "candidate_raw": raw_name,
                "age": number(row[start + field_offsets["age"]] if start + field_offsets["age"] < len(row) else None),
                "party": compact(row[start + field_offsets["party"]] if start + field_offsets["party"] < len(row) else None),
                "candidate_status": _STATUS_MAP.get(status),
                "occupation": compact(row[start + field_offsets["occupation"]] if start + field_offsets["occupation"] < len(row) else None),
                "elected": label == "当",
                "metric": "candidate_votes",
                "value": votes,
                "unit": "votes",
            })
            if "gender" in field_offsets:
                gender = compact(row[start + field_offsets["gender"]] if start + field_offsets["gender"] < len(row) else None)
                if gender in {"男", "男性"}:
                    fact["gender"] = "male"
                elif gender in {"女", "女性"}:
                    fact["gender"] = "female"
            if byelection:
                fact["row_variant"] = f"byelection_seats:{byelection}"
            output.append(fact)
    return _attach_chamber(output)


def _party_from_sangiin_doc(doc: dict[str, Any], table: list[list[Any]]) -> str:
    from soumu_election.normalize import compact

    for row in table[:8]:
        label = compact(row[0] if row else None)
        if label.startswith("政党等の名称"):
            return label.removeprefix("政党等の名称")
    source_file = str(doc.get("source_file") or "")
    # unclassified_自由民主党_001027837.xlsx
    name = source_file.replace("\\", "/").split("/")[-1]
    if name.startswith("unclassified_"):
        body = name[len("unclassified_"):]
        party = body.rsplit("_", 1)[0]
        return party.replace("NHK党", "ＮＨＫ党")
    return ""


def _is_list_person_header(name: str) -> bool:
    if not name:
        return False
    if name.startswith(("小計", "政党", "得票", "名簿")):
        return False
    if "得票" in name or "率" in name:
        return False
    return True


def parse_sangiin_pr_list_by_prefecture(doc: dict[str, Any], sheet: dict[str, Any], table: list[list[Any]]) -> list[dict[str, Any]]:
    """unclassified_* = （11）都道府県別党派別名簿登載者別得票数。"""
    from soumu_election.normalize import PREFECTURE, base, candidate_name, compact, number

    party = _party_from_sangiin_doc(doc, table)
    if not party:
        return []
    output: list[dict[str, Any]] = []
    row_index = 0
    while row_index < len(table):
        row = table[row_index]
        if compact(row[0] if row else None) != "名簿登載者名":
            row_index += 1
            continue
        people: list[tuple[int, str, str, bool | None]] = []
        for col, value in enumerate(row[1:], start=1):
            raw = str(value or "").strip()
            label = compact(raw)
            if not _is_list_person_header(label):
                continue
            name, raw_name = candidate_name(raw)
            if not name:
                continue
            people.append((col, name, raw_name, None))
        if not people:
            row_index += 1
            continue

        # 当落行（任意）
        elected_index = row_index + 1
        if elected_index < len(table) and compact(table[elected_index][0] if table[elected_index] else None) == "当落":
            elected_row = table[elected_index]
            updated = []
            for col, name, raw_name, _ in people:
                mark = compact(elected_row[col] if col < len(elected_row) else None)
                elected = True if mark == "当" else False if mark == "落" else None
                updated.append((col, name, raw_name, elected))
            people = updated
            data_start = elected_index + 1
        else:
            data_start = row_index + 1

        cursor = data_start
        while cursor < len(table):
            data_row = table[cursor]
            label0 = compact(data_row[0] if data_row else None)
            if label0 in {"順位", "名簿登載者名", "当落"}:
                break
            if label0.startswith("政党等の名称"):
                break
            if PREFECTURE.search(label0) or label0 in {"計", "合計", "全国"}:
                for col, name, raw_name, elected in people:
                    value = number(data_row[col] if col < len(data_row) else None)
                    if value is None:
                        continue
                    fact = base(doc, sheet, cursor, col)
                    fact.update({
                        "contest": "pr",
                        "prefecture": label0,
                        "party": party,
                        "candidate": name,
                        "candidate_raw": raw_name,
                        "elected": elected,
                        "metric": "candidate_votes",
                        "value": value,
                        "unit": "votes",
                        "source_code": "03-11",
                    })
                    output.append(fact)
            cursor += 1
        row_index = cursor
    return _attach_chamber(output)


SANGIIN_PARSERS = {
    "02-01": parse_sangiin_people,
    "02-01-cmp": parse_sangiin_rates,
    "02-02": parse_sangiin_people,
    "02-02-cmp": parse_sangiin_rates,
    "03-03": parse_sangiin_party_comparison,
    "03-04": parse_sangiin_party_comparison,
    "03-05": parse_sangiin_pr_prefecture_party,
    "03-06": parse_sangiin_prefecture_party_gender,
    "03-07": parse_sangiin_ballots,
    "03-08": parse_sangiin_ballots,
    "03-09": parse_sangiin_pr_ranking,
    "03-10": parse_sangiin_pr_list_candidates,
    "03-11": parse_sangiin_pr_list_by_prefecture,
    "03-13": parse_sangiin_district_candidates,
}
