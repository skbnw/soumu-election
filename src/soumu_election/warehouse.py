#!/usr/bin/env python3
"""Build the cross-election DuckDB and Parquet dataset from normalized JSON."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb


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

FACT_COLUMNS = (
    "fact_id", "source_id", "election_id", "election_kaiji", "contest", "scope",
    "prefecture_code", "prefecture", "pr_block", "party", "justice", "gender",
    "age_band", "candidate_status", "row_variant", "metric", "value", "unit",
    "divisor", "allocation_rank", "source_code", "dataset", "source_url",
    "source_file", "source_sheet", "source_cell",
    "candidate", "candidate_raw", "district_number", "elected", "age", "occupation",
    "dual_candidacy", "sekihairitsu",
)


def stable_id(prefix: str, *values: Any) -> str:
    raw = "\x1f".join("" if value is None else str(value) for value in values)
    return f"{prefix}_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:24]}"


def fact_row(item: dict[str, Any]) -> tuple[Any, ...]:
    election_id = f"shugiin-{item['election_kaiji']}"
    source_id = stable_id("src", election_id, item["source_file"])
    identity = [item.get(key) for key in (
        "election_kaiji", "source_file", "source_sheet", "source_cell", "contest",
        "prefecture", "pr_block", "party", "justice", "gender", "age_band",
        "candidate_status", "row_variant", "candidate", "district_number", "metric")]
    values = {
        **item,
        "fact_id": stable_id("fact", *identity),
        "source_id": source_id,
        "election_id": election_id,
        "prefecture_code": PREFECTURE_CODES.get(item.get("prefecture")),
    }
    return tuple(values.get(column) for column in FACT_COLUMNS)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build DuckDB and Parquet election warehouse")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    parser.add_argument("--kaiji", type=int, nargs="*", default=list(range(44, 52)))
    args = parser.parse_args()
    root = args.project_root.resolve()
    output = (args.output or root / "data" / "warehouse").resolve()
    parquet = output / "parquet"
    output.mkdir(parents=True, exist_ok=True)
    parquet.mkdir(parents=True, exist_ok=True)
    db_path = output / "soumu_election.duckdb"
    if db_path.exists():
        db_path.unlink()

    elections, sources, coverage, facts = [], {}, [], []
    for kaiji in args.kaiji:
        config_path = root / "config" / f"shugiin{kaiji}.json"
        fact_path = root / "data" / f"shugiin{kaiji}" / "normalized" / "facts.json"
        norm_manifest_path = fact_path.parent / "manifest.json"
        if not (config_path.exists() and fact_path.exists() and norm_manifest_path.exists()):
            raise FileNotFoundError(f"required input missing for shugiin{kaiji}")
        config = json.loads(config_path.read_text(encoding="utf-8"))
        norm_manifest = json.loads(norm_manifest_path.read_text(encoding="utf-8"))
        elections.append((f"shugiin-{kaiji}", "shugiin", kaiji, config.get("election_date")))
        for entry in norm_manifest["coverage"]:
            coverage.append((f"shugiin-{kaiji}", kaiji, entry["source_code"],
                             entry.get("dataset"), entry["status"], entry["records"]))
        for item in json.loads(fact_path.read_text(encoding="utf-8")):
            row = fact_row(item)
            facts.append(row)
            source_id = row[1]
            sources[source_id] = (source_id, f"shugiin-{kaiji}", kaiji, item["source_code"],
                                  item["dataset"], item["source_url"], item["source_file"])

    facts_ndjson = output / ".facts.ndjson"
    with facts_ndjson.open("w", encoding="utf-8") as handle:
        for row in facts:
            handle.write(json.dumps(dict(zip(FACT_COLUMNS, row)), ensure_ascii=False) + "\n")

    con = duckdb.connect(str(db_path))
    con.execute("CREATE TABLE elections(election_id VARCHAR PRIMARY KEY, election_type VARCHAR, election_kaiji INTEGER, election_date DATE)")
    con.execute("CREATE TABLE source_documents(source_id VARCHAR PRIMARY KEY, election_id VARCHAR, election_kaiji INTEGER, source_code VARCHAR, dataset VARCHAR, source_url VARCHAR, source_file VARCHAR)")
    con.execute("CREATE TABLE normalization_coverage(election_id VARCHAR, election_kaiji INTEGER, source_code VARCHAR, dataset VARCHAR, status VARCHAR, records BIGINT)")
    facts_source = facts_ndjson.as_posix().replace("'", "''")
    con.execute(f"""CREATE TABLE facts AS SELECT
        fact_id::VARCHAR AS fact_id, source_id::VARCHAR AS source_id,
        election_id::VARCHAR AS election_id, election_kaiji::INTEGER AS election_kaiji,
        contest::VARCHAR AS contest, scope::VARCHAR AS scope,
        prefecture_code::VARCHAR AS prefecture_code, prefecture::VARCHAR AS prefecture,
        pr_block::VARCHAR AS pr_block, party::VARCHAR AS party, justice::VARCHAR AS justice,
        gender::VARCHAR AS gender, age_band::VARCHAR AS age_band,
        candidate_status::VARCHAR AS candidate_status, row_variant::VARCHAR AS row_variant,
        metric::VARCHAR AS metric, value::DOUBLE AS value, unit::VARCHAR AS unit,
        divisor::BIGINT AS divisor, allocation_rank::BIGINT AS allocation_rank,
        source_code::VARCHAR AS source_code, dataset::VARCHAR AS dataset,
        source_url::VARCHAR AS source_url, source_file::VARCHAR AS source_file,
        source_sheet::VARCHAR AS source_sheet, source_cell::VARCHAR AS source_cell,
        candidate::VARCHAR AS candidate, candidate_raw::VARCHAR AS candidate_raw,
        district_number::INTEGER AS district_number, elected::BOOLEAN AS elected,
        age::INTEGER AS age, occupation::VARCHAR AS occupation,
        dual_candidacy::BOOLEAN AS dual_candidacy, sekihairitsu::DOUBLE AS sekihairitsu
        FROM read_json_auto('{facts_source}', format='newline_delimited', union_by_name=true)""")
    con.executemany("INSERT INTO elections VALUES (?, ?, ?, ?)", elections)
    con.executemany("INSERT INTO source_documents VALUES (?, ?, ?, ?, ?, ?, ?)", list(sources.values()))
    con.executemany("INSERT INTO normalization_coverage VALUES (?, ?, ?, ?, ?, ?)", coverage)

    con.execute("""CREATE VIEW judicial_review_results AS
        SELECT election_id, election_kaiji, prefecture_code, prefecture, justice,
          max(value) FILTER (WHERE metric='dismissal_yes') AS dismissal_yes,
          max(value) FILTER (WHERE metric='dismissal_no') AS dismissal_no,
          max(value) FILTER (WHERE metric='invalid_mark') AS invalid_mark,
          max(value) FILTER (WHERE metric='review_votes_total') AS review_votes_total
        FROM facts WHERE contest='judicial_review' AND source_code='05-02'
        GROUP BY ALL""")
    con.execute("CREATE TABLE validation_results(check_name VARCHAR, status VARCHAR, failures BIGINT, details VARCHAR)")
    duplicate_facts = con.execute("SELECT count(*)-count(DISTINCT fact_id) FROM facts").fetchone()[0]
    missing_sources = con.execute("SELECT count(*) FROM facts f ANTI JOIN source_documents s USING(source_id)").fetchone()[0]
    judicial_failures = con.execute("""SELECT count(*) FROM judicial_review_results
        WHERE dismissal_yes + dismissal_no + invalid_mark <> review_votes_total""").fetchone()[0]
    ballot_failures = con.execute("""WITH wide AS (
        SELECT election_kaiji, source_file, source_sheet, prefecture, pr_block,
          max(value) FILTER (WHERE metric='ballots_cast') AS cast_count,
          max(value) FILTER (WHERE metric='valid_ballots') AS valid_count,
          max(value) FILTER (WHERE metric='invalid_ballots') AS invalid_count
        FROM facts WHERE source_code IN ('03-08','03-09','05-03') GROUP BY ALL)
        SELECT count(*) FROM wide WHERE cast_count IS NOT NULL
          AND cast_count <> valid_count + invalid_count""").fetchone()[0]
    people_failures = con.execute("""WITH wide AS (
        SELECT election_kaiji, source_file, source_sheet, contest, scope, prefecture, pr_block,
          max(value) FILTER (WHERE metric='eligible_voters' AND gender='male') AS eligible_male,
          max(value) FILTER (WHERE metric='eligible_voters' AND gender='female') AS eligible_female,
          max(value) FILTER (WHERE metric='eligible_voters' AND gender='total') AS eligible_total,
          max(value) FILTER (WHERE metric='voters' AND gender='male') AS voters_male,
          max(value) FILTER (WHERE metric='voters' AND gender='female') AS voters_female,
          max(value) FILTER (WHERE metric='voters' AND gender='total') AS voters_total,
          max(value) FILTER (WHERE metric='abstentions' AND gender='male') AS abstentions_male,
          max(value) FILTER (WHERE metric='abstentions' AND gender='female') AS abstentions_female,
          max(value) FILTER (WHERE metric='abstentions' AND gender='total') AS abstentions_total
        FROM facts GROUP BY ALL)
        SELECT count(*) FROM wide WHERE eligible_total IS NOT NULL AND
          (eligible_male + eligible_female <> eligible_total OR
           voters_male + voters_female <> voters_total OR
           abstentions_male + abstentions_female <> abstentions_total OR
           eligible_male <> voters_male + abstentions_male OR
           eligible_female <> voters_female + abstentions_female OR
           eligible_total <> voters_total + abstentions_total)""").fetchone()[0]
    candidate_vote_failures = con.execute("""WITH candidates AS (
          SELECT election_kaiji, prefecture, sum(value) AS votes FROM facts
          WHERE metric='candidate_votes' GROUP BY ALL), ballots AS (
          SELECT election_kaiji, prefecture, max(value) AS valid_votes FROM facts
          WHERE source_code='03-08' AND metric='valid_ballots' AND prefecture NOT IN ('計','合計') GROUP BY ALL)
        SELECT count(*) FROM candidates JOIN ballots USING(election_kaiji,prefecture)
        WHERE abs(votes-valid_votes) > 0.1""").fetchone()[0]
    pr_vote_failures = con.execute("""WITH ranked AS (
          SELECT election_kaiji, pr_block, party, value FROM facts
          WHERE election_kaiji=44 AND source_code='03-10' AND metric='party_votes'), elected AS (
          SELECT election_kaiji, pr_block, party, value FROM facts
          WHERE election_kaiji=44 AND source_code='03-11' AND metric='party_votes')
        SELECT count(*) FROM ranked FULL JOIN elected USING(election_kaiji,pr_block,party)
        WHERE ranked.value IS DISTINCT FROM elected.value""").fetchone()[0]
    pr_seat_failures = con.execute("""WITH elected AS (
          SELECT election_kaiji, pr_block, sum(value) AS seats FROM facts
          WHERE election_kaiji=44 AND source_code='03-11' AND metric='elected_candidates' AND gender='total' GROUP BY ALL),
        allocated AS (SELECT election_kaiji, pr_block, count(*) AS seats FROM facts
          WHERE election_kaiji=44 AND source_code='03-12' AND allocation_rank IS NOT NULL GROUP BY ALL)
        SELECT count(*) FROM elected FULL JOIN allocated USING(election_kaiji,pr_block)
        WHERE elected.seats IS DISTINCT FROM allocated.seats""").fetchone()[0]
    checks = [
        ("fact_id_unique", "pass" if duplicate_facts == 0 else "fail", duplicate_facts, "fact_id must be unique"),
        ("source_reference", "pass" if missing_sources == 0 else "fail", missing_sources, "every fact must reference source_documents"),
        ("judicial_review_arithmetic", "pass" if judicial_failures == 0 else "fail", judicial_failures, "yes + no + invalid = total"),
        ("ballot_arithmetic", "pass" if ballot_failures == 0 else "fail", ballot_failures, "valid + invalid = ballots cast"),
        ("people_arithmetic", "pass" if people_failures == 0 else "fail", people_failures, "male + female = total; voters + abstentions = eligible"),
        ("candidate_votes_to_valid_ballots", "pass" if candidate_vote_failures == 0 else "fail", candidate_vote_failures, "candidate vote sum = prefecture valid ballots"),
        ("pr_vote_source_agreement", "pass" if pr_vote_failures == 0 else "fail", pr_vote_failures, "03-10 party votes = 03-11 party votes"),
        ("pr_seat_allocation", "pass" if pr_seat_failures == 0 else "fail", pr_seat_failures, "elected seats = allocated ranks"),
    ]
    con.executemany("INSERT INTO validation_results VALUES (?, ?, ?, ?)", checks)
    for table in ("elections", "source_documents", "normalization_coverage", "facts", "validation_results"):
        target = (parquet / f"{table}.parquet").as_posix().replace("'", "''")
        con.execute(f"COPY {table} TO '{target}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    counts = {table: con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
              for table in ("elections", "source_documents", "normalization_coverage", "facts", "validation_results")}
    manifest = {
        "schema_version": "1.0", "generated_at": datetime.now(timezone.utc).isoformat(),
        "election_kaiji": args.kaiji, "database": db_path.name, "counts": counts,
        "validation": {name: status for name, status, _, _ in checks},
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    web_meta = root / "web" / "data" / "meta.json"
    if web_meta.parent.exists():
        web_meta.write_text(json.dumps({
            "generated_at": manifest["generated_at"],
            "election_kaiji": args.kaiji,
            "facts": counts.get("facts"),
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    con.close()
    facts_ndjson.unlink(missing_ok=True)
    print(json.dumps(manifest, ensure_ascii=False))
    return 0 if all(status == "pass" for _, status, _, _ in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
