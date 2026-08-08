# v1.0.0: 参院（sangiin）専用正規化パーサ。衆院 PARSERS とは項番の意味が衝突するため分離。
"""House of Councillors (sangiin) semantic parsers."""
from __future__ import annotations

from typing import Any

# Reuse helpers from normalize without circular import at module load:
# callers pass already-imported callables / we import inside functions.


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


SANGIIN_PARSERS = {
    "02-01": parse_sangiin_people,
    "02-01-cmp": parse_sangiin_rates,
    "02-02": parse_sangiin_people,
    "02-02-cmp": parse_sangiin_rates,
    "03-03": parse_sangiin_party_comparison,
    "03-04": parse_sangiin_party_comparison,
    "03-06": parse_sangiin_prefecture_party_gender,
    "03-07": parse_sangiin_ballots,
    "03-08": parse_sangiin_ballots,
}
