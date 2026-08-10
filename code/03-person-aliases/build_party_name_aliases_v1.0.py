# -*- coding: utf-8 -*-
"""
build_party_name_aliases_v1.0.py
- MIC 正式名と政治学会略称などの政党別名マップ（表示・検索用）
- 数値正本は触らない。原本 CSV/JSONL は改変しない
- 優先: 手動 overrides → 既知シード → 同一回で一意な包含一致

出力:
  web/data/party_name_aliases.parquet
  data/warehouse/parquet/party_name_aliases.parquet
  output/03-person-aliases/*_party_alias_report.txt
"""
from __future__ import annotations

import json
import unicodedata
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parents[2]
OVERRIDES = Path(__file__).resolve().parent / "party_name_overrides.json"
FACTS = REPO / "web" / "data" / "facts.parquet"
SEIJI_PR = REPO / "web" / "data" / "seiji_gakkai_pr_votes.parquet"
SEIJI_SMD = REPO / "web" / "data" / "seiji_gakkai_smd_district_votes.parquet"
OUT_DIR = REPO / "output" / "03-person-aliases"
WEB_OUT = REPO / "web" / "data" / "party_name_aliases.parquet"
WAREHOUSE_OUT = REPO / "data" / "warehouse" / "parquet" / "party_name_aliases.parquet"

# グローバル既知対応（選挙回で意味がぶれにくいもの）
SEED_GLOBAL: dict[str, str] = {
    "自民": "自由民主党",
    "自由民主党": "自由民主党",
    "公明": "公明党",
    "公明党": "公明党",
    "共産": "日本共産党",
    "日本共産党": "日本共産党",
    "社民": "社会民主党",
    "社会": "社会民主党",
    "社会民主党": "社会民主党",
    "民主": "民主党",
    "民主党": "民主党",
    "みな": "みんなの党",
    "みんな": "みんなの党",
    "みんなの党": "みんなの党",
    "幸福": "幸福実現党",
    "幸福実現党": "幸福実現党",
    "大地": "新党大地",
    "新党大地": "新党大地",
    "希望の党": "希望の党",
    "希望": "希望の党",
    "立憲民主党": "立憲民主党",
    "立憲": "立憲民主党",
    "支持なし": "支持政党なし",
    "支持政党なし": "支持政党なし",
    "日本のこころ": "日本のこころ",
    "次世代": "次世代の党",
    "次世代の党": "次世代の党",
    "生活": "生活の党",
    "生活の党": "生活の党",
    "本質": "新党本質",
    "新党本質": "新党本質",
    "日本": "新党日本",
    "新党日本": "新党日本",
    "未来": "日本未来の党",
    "日本未来の党": "日本未来の党",
    "維新": "日本維新の会",  # 既定。回別 override で維新の党へ
    "日本維新の会": "日本維新の会",
    "維新の党": "維新の党",
    "国民": "国民新党",  # 既定（〜2010s）。国民民主は override
    "国民新党": "国民新党",
    "国民民主党": "国民民主党",
    "改ク": "改革クラブ",
    "改革クラブ": "改革クラブ",
    "改革": "新党改革",
    "新党改革": "新党改革",
    "新進": "新進党",
    "新進党": "新進党",
    "さきがけ": "新党さきがけ",
    "新党さきがけ": "新党さきがけ",
    "保守": "保守党",
    "保守党": "保守党",
    "自由": "自由党",
    "自由党": "自由党",
    "れいわ新選組": "れいわ新選組",
    "参政党": "参政党",
    "日本保守党": "日本保守党",
}

# 選挙回別の上書き（略称→正本）
SEED_BY_KAIJI: dict[int, dict[str, str]] = {
    47: {
        "維新": "維新の党",
    },
    49: {
        "国民": "国民民主党",
    },
    50: {
        "国民": "国民民主党",
    },
    51: {
        "国民": "国民民主党",
    },
}


def nfkc(value: str | None) -> str:
    return unicodedata.normalize("NFKC", str(value or "").strip())


def load_overrides() -> tuple[dict[str, str], dict[tuple[int, str], str]]:
    global_map: dict[str, str] = {}
    by_kaiji: dict[tuple[int, str], str] = {}
    if not OVERRIDES.is_file():
        return global_map, by_kaiji
    data = json.loads(OVERRIDES.read_text(encoding="utf-8"))
    for row in data.get("global") or []:
        alias = nfkc(row.get("alias"))
        canon = nfkc(row.get("canonical"))
        if alias and canon:
            global_map[alias] = canon
    for row in data.get("by_kaiji") or []:
        try:
            th = int(row.get("election_kaiji"))
        except (TypeError, ValueError):
            continue
        alias = nfkc(row.get("alias"))
        canon = nfkc(row.get("canonical"))
        if alias and canon:
            by_kaiji[(th, alias)] = canon
    return global_map, by_kaiji


def load_parties() -> tuple[set[str], set[str], dict[int, set[str]], dict[int, set[str]]]:
    con = duckdb.connect()
    mic_all: set[str] = set()
    seiji_all: set[str] = set()
    mic_by: dict[int, set[str]] = defaultdict(set)
    seiji_by: dict[int, set[str]] = defaultdict(set)

    if FACTS.is_file():
        rows = con.execute(
            f"""
            SELECT DISTINCT election_kaiji, party
            FROM read_parquet('{FACTS.as_posix()}')
            WHERE election_id LIKE 'shugiin-%'
              AND contest = 'pr'
              AND metric IN ('party_votes', 'current_votes')
              AND coalesce(party, '') NOT IN ('', '合計', '計', '諸派')
            """
        ).fetchall()
        for k, p in rows:
            name = nfkc(p)
            if not name:
                continue
            mic_all.add(name)
            mic_by[int(k)].add(name)

    for path in (SEIJI_PR, SEIJI_SMD):
        if not path.is_file():
            continue
        metric = "party_votes" if path == SEIJI_PR else "candidate_votes"
        col = "party"
        rows = con.execute(
            f"""
            SELECT DISTINCT election_kaiji, {col}
            FROM read_parquet('{path.as_posix()}')
            WHERE metric = '{metric}'
              AND coalesce({col}, '') NOT IN ('', '合計', '計')
            """
        ).fetchall()
        for k, p in rows:
            name = nfkc(p)
            if not name:
                continue
            seiji_all.add(name)
            seiji_by[int(k)].add(name)

    return mic_all, seiji_all, mic_by, seiji_by


def resolve_canonical(
    alias: str,
    *,
    kaiji: int | None,
    ov_global: dict[str, str],
    ov_kaiji: dict[tuple[int, str], str],
    mic_names: set[str],
) -> tuple[str, str]:
    """Return (canonical, method)."""
    if kaiji is not None and (kaiji, alias) in ov_kaiji:
        return ov_kaiji[(kaiji, alias)], "override_kaiji"
    if alias in ov_global:
        return ov_global[alias], "override_global"
    if kaiji is not None and kaiji in SEED_BY_KAIJI and alias in SEED_BY_KAIJI[kaiji]:
        return SEED_BY_KAIJI[kaiji][alias], "seed_kaiji"
    if alias in SEED_GLOBAL:
        return SEED_GLOBAL[alias], "seed_global"
    if alias in mic_names:
        return alias, "mic_exact"
    # 「X」↔「X党」の一意対応のみ（包含の広め突合は誤結合しやすいのでしない）
    party_suffix = alias + "党"
    if party_suffix in mic_names:
        return party_suffix, "alias_plus_tou"
    return alias, "passthrough"


def main() -> None:
    ov_global, ov_kaiji = load_overrides()
    mic_all, seiji_all, mic_by, seiji_by = load_parties()
    names = sorted(mic_all | seiji_all)

    rows: list[dict] = []
    seen: set[tuple[str | None, str]] = set()
    methods = defaultdict(int)

    # グローバル別名（回非依存）
    for alias in names:
        canon, method = resolve_canonical(
            alias, kaiji=None, ov_global=ov_global, ov_kaiji=ov_kaiji, mic_names=mic_all
        )
        key = (None, alias)
        if key in seen:
            continue
        seen.add(key)
        methods[method] += 1
        rows.append(
            {
                "election_kaiji": None,
                "alias_name": alias,
                "canonical_name": canon,
                "match_method": method,
                "source": "party-name-aliases",
            }
        )

    # 回別（シード/override があるもの＋その回の MIC/seiji 名）
    kaijis = sorted(set(mic_by) | set(seiji_by) | set(SEED_BY_KAIJI) | {k for k, _ in ov_kaiji})
    for th in kaijis:
        mic_names = mic_by.get(th) or mic_all
        local_names = sorted((mic_by.get(th) or set()) | (seiji_by.get(th) or set()))
        # 回別シード・override の alias も必ず載せる
        extra = set(SEED_BY_KAIJI.get(th, {})) | {a for (k, a) in ov_kaiji if k == th}
        for alias in sorted(set(local_names) | extra):
            canon, method = resolve_canonical(
                alias, kaiji=th, ov_global=ov_global, ov_kaiji=ov_kaiji, mic_names=mic_names
            )
            key = (th, alias)
            if key in seen:
                continue
            # グローバルと同じなら回別行は省略可だが、回別上書きは残す
            if method not in {"override_kaiji", "seed_kaiji"} and (None, alias) in {(None, r["alias_name"]) for r in rows if r["election_kaiji"] is None and r["canonical_name"] == canon}:
                # still add if canonical differs from global
                g_canon, _ = resolve_canonical(
                    alias, kaiji=None, ov_global=ov_global, ov_kaiji=ov_kaiji, mic_names=mic_all
                )
                if g_canon == canon:
                    continue
            seen.add(key)
            methods[method] += 1
            rows.append(
                {
                    "election_kaiji": th,
                    "alias_name": alias,
                    "canonical_name": canon,
                    "match_method": method,
                    "source": "party-name-aliases",
                }
            )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    staging = OUT_DIR / f"{stamp}_party_name_aliases.jsonl"
    with staging.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    (OUT_DIR / "party_name_aliases.jsonl").write_text(staging.read_text(encoding="utf-8"), encoding="utf-8")

    WAREHOUSE_OUT.parent.mkdir(parents=True, exist_ok=True)
    WEB_OUT.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(
        f"""
        COPY (
          SELECT * FROM read_json_auto('{staging.as_posix()}')
          ORDER BY election_kaiji NULLS FIRST, canonical_name, alias_name
        ) TO '{WAREHOUSE_OUT.as_posix()}' (FORMAT PARQUET)
        """
    )
    WEB_OUT.write_bytes(WAREHOUSE_OUT.read_bytes())

    # 突合サンプル: seiji 略称が MIC 正本に寄ったか
    sample_lines = []
    for th in range(41, 49):
        for alias in sorted(seiji_by.get(th) or []):
            canon, method = resolve_canonical(
                alias, kaiji=th, ov_global=ov_global, ov_kaiji=ov_kaiji, mic_names=mic_by.get(th) or mic_all
            )
            if alias != canon:
                sample_lines.append(f"- th={th} {alias} -> {canon} ({method})")

    report = OUT_DIR / f"{stamp}_party_alias_report.txt"
    lines = [
        "# party name aliases",
        f"generated_at={datetime.now().isoformat(timespec='seconds')}",
        f"rows={len(rows)}",
        f"web_out={WEB_OUT}",
        f"overrides={OVERRIDES if OVERRIDES.is_file() else '(none)'}",
        "",
        "## methods",
        *[f"- {k}: {v}" for k, v in sorted(methods.items())],
        "",
        "## seiji→canonical samples (41-48, changed only)",
        *sample_lines[:80],
        "",
        "OK",
    ]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUT_DIR / "party_alias_report.txt").write_text(report.read_text(encoding="utf-8"), encoding="utf-8")
    print(report.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
