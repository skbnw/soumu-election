# -*- coding: utf-8 -*-
"""
build_person_name_aliases.py v1.2
- v1.2: 同一 giin_cd に別人名が混入する読売CSV誤りを、国会議員白書名で補正
        （例: 2021山口3区・林芳正 に誤付与された r02187=安倍晋三）
- v1.1: MIC は選挙区内の氏名突合のみ（別人名の混入を防止）
- v1.0: 読売紙面名（giin_cd=r#####）を人物正本キーにする
- 国会議員白書（kokkai.sugawarataku.net）の漢字・かなを別名登録
- 総務省 facts の異体字/IVS/かな混じり表記を別名登録
- 検証ケース: 逢坂誠二（r02606）— おおさか誠二 / PUA・IVS 付き表記
           林芳正（r03160）が安倍晋三（r02187）へ誤表示されないこと

出力:
  output/03-person-aliases/YYYYMMDD_HHMM_person_name_aliases.jsonl
  output/03-person-aliases/person_name_aliases.jsonl（最新）
  web/data/person_name_aliases.parquet
"""
from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parents[2]
YOMI_CSV = REPO / "references" / "yomi-shosenkyo" / "yomi-election-data-1996-2026.csv"
KOKKAI_ROOT = REPO / "references" / "kokkai.sugawarataku.net"
FACTS = REPO / "web" / "data" / "facts.parquet"
OUT_DIR = REPO / "output" / "03-person-aliases"
WEB_OUT = REPO / "web" / "data" / "person_name_aliases.parquet"

GIIN_RE = re.compile(r"^r\d+$", re.I)
HREF_RE = re.compile(r"/giin/(r\d+)\.html", re.I)
IVS_RE = re.compile(r"[\uFE00-\uFE0F\U000E0100-\U000E01EF]")
PUA_RE = re.compile(r"[\uE000-\uF8FF]")
SPACE_RE = re.compile(r"[\s\u3000]+")

PREF_BY_NUM = {
    1: "北海道", 2: "青森県", 3: "岩手県", 4: "宮城県", 5: "秋田県", 6: "山形県", 7: "福島県",
    8: "茨城県", 9: "栃木県", 10: "群馬県", 11: "埼玉県", 12: "千葉県", 13: "東京都", 14: "神奈川県",
    15: "新潟県", 16: "富山県", 17: "石川県", 18: "福井県", 19: "山梨県", 20: "長野県",
    21: "岐阜県", 22: "静岡県", 23: "愛知県", 24: "三重県", 25: "滋賀県", 26: "京都府", 27: "大阪府",
    28: "兵庫県", 29: "奈良県", 30: "和歌山県", 31: "鳥取県", 32: "島根県", 33: "岡山県",
    34: "広島県", 35: "山口県", 36: "徳島県", 37: "香川県", 38: "愛媛県", 39: "高知県",
    40: "福岡県", 41: "佐賀県", 42: "長崎県", 43: "熊本県", 44: "大分県", 45: "宮崎県",
    46: "鹿児島県", 47: "沖縄県",
}

_LAST_YOMI_CORRECTIONS = 0


def normalize_name(value: str | None) -> str:
    if not value:
        return ""
    s = str(value)
    s = IVS_RE.sub("", s)
    s = unicodedata.normalize("NFKC", s)
    s = SPACE_RE.sub("", s)
    return s


def normalize_name_soft(value: str | None) -> str:
    return PUA_RE.sub("", normalize_name(value))


def kana_compact(value: str | None) -> str:
    s = normalize_name(value)
    return "".join(ch for ch in s if "ぁ" <= ch <= "ん" or "ァ" <= ch <= "ン" or ch == "ー")


def add_alias(bucket: dict[tuple[str, str], dict], person_id: str, alias: str, source: str, canonical: str) -> None:
    alias = (alias or "").strip()
    if not alias:
        return
    key = (person_id, alias)
    if key in bucket:
        prev = bucket[key]
        sources = set(prev["source"].split("|"))
        sources.add(source)
        prev["source"] = "|".join(sorted(sources))
        return
    norms = {normalize_name(alias), normalize_name_soft(alias)}
    norms.discard("")
    bucket[key] = {
        "person_id": person_id,
        "canonical_name": canonical,
        "alias_name": alias,
        "alias_normalized": normalize_name(alias),
        "alias_normalized_soft": normalize_name_soft(alias),
        "source": source,
    }
    for n in norms:
        if n != alias:
            nkey = (person_id, n)
            if nkey not in bucket:
                bucket[nkey] = {
                    "person_id": person_id,
                    "canonical_name": canonical,
                    "alias_name": n,
                    "alias_normalized": n,
                    "alias_normalized_soft": normalize_name_soft(n),
                    "source": f"{source}|normalized",
                }


def load_kokkai() -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    for folder in (KOKKAI_ROOT / "shugiin", KOKKAI_ROOT / "sangiin"):
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.csv")):
            with path.open(encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f):
                    href = row.get("zt5 href") or row.get("href") or ""
                    m = HREF_RE.search(href)
                    if not m:
                        continue
                    pid = m.group(1).lower()
                    kanji = (row.get("zt5") or row.get("name") or "").strip()
                    kana = (row.get("zt4") or row.get("kana") or "").strip()
                    out.append((pid, kanji, kana))
    return out


def kokkai_name_index(kokkai: list[tuple[str, str, str]]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    for pid, kanji, _kana in kokkai:
        n = normalize_name(kanji)
        if n:
            out[n].add(pid)
    return out


def resolve_yomi_person_id(
    csv_giin_cd: str | None,
    name: str,
    kokkai_by_name: dict[str, set[str]],
) -> str | None:
    name_ids = kokkai_by_name.get(normalize_name(name)) or set()
    csv_id = csv_giin_cd.lower() if csv_giin_cd and GIIN_RE.fullmatch(csv_giin_cd) else None
    if len(name_ids) == 1:
        return next(iter(name_ids))
    return csv_id


def load_yomi(
    kokkai_by_name: dict[str, set[str]],
) -> tuple[dict[str, str], list[dict], dict[tuple[int, str, int], list[tuple[str, str]]]]:
    global _LAST_YOMI_CORRECTIONS
    by_id_names: dict[str, list[tuple[int, str]]] = defaultdict(list)
    rows: list[dict] = []
    district_cands: dict[tuple[int, str, int], list[tuple[str, str]]] = defaultdict(list)
    name_to_ids: dict[str, set[str]] = defaultdict(set)
    corrections = 0

    with YOMI_CSV.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            name = (row.get("candidate_name") or "").strip()
            if not name:
                continue
            cd = (row.get("giin_cd") or "").strip()
            try:
                th = int(float(str(row.get("th") or "").strip()))
            except ValueError:
                continue
            try:
                pref_num = int(float(str(row.get("pref_num") or "").strip()))
                dist_num = int(float(str(row.get("district_num") or "").strip()))
            except ValueError:
                pref_num = dist_num = None

            person_id = resolve_yomi_person_id(cd, name, kokkai_by_name)
            if person_id and GIIN_RE.fullmatch(cd or "") and person_id != cd.lower():
                corrections += 1

            if person_id:
                by_id_names[person_id].append((th, name))
                name_to_ids[normalize_name(name)].add(person_id)
                rows.append(
                    {
                        "th": th,
                        "name": name,
                        "person_id": person_id,
                        "pref_num": pref_num,
                        "district_num": dist_num,
                    }
                )
                if pref_num and dist_num and pref_num in PREF_BY_NUM:
                    district_cands[(th, PREF_BY_NUM[pref_num], dist_num)].append((person_id, name))
            else:
                rows.append(
                    {
                        "th": th,
                        "name": name,
                        "person_id": None,
                        "pref_num": pref_num,
                        "district_num": dist_num,
                    }
                )

    for r in rows:
        if r["person_id"]:
            continue
        ids = set(name_to_ids.get(normalize_name(r["name"])) or set())
        ids |= set(kokkai_by_name.get(normalize_name(r["name"])) or set())
        if len(ids) != 1:
            continue
        r["person_id"] = next(iter(ids))
        pref_num, dist_num = r["pref_num"], r["district_num"]
        if pref_num and dist_num and pref_num in PREF_BY_NUM:
            district_cands[(r["th"], PREF_BY_NUM[pref_num], dist_num)].append((r["person_id"], r["name"]))

    canonical: dict[str, str] = {}
    for pid, items in by_id_names.items():
        items.sort(key=lambda x: x[0])
        preferred = None
        for _th, nm in reversed(items):
            kids = kokkai_by_name.get(normalize_name(nm)) or set()
            if kids == {pid}:
                preferred = nm
                break
        canonical[pid] = preferred or items[-1][1]

    _LAST_YOMI_CORRECTIONS = corrections
    return canonical, rows, district_cands


def extract_raw_aliases(raw: str) -> list[str]:
    if not raw:
        return []
    aliases: list[str] = []
    for line in [ln.strip() for ln in raw.replace("\r", "\n").split("\n") if ln.strip()]:
        aliases.append(line)
        paren = re.search(r"[（(]\s*([^）)]+?)\s*[）)]", line)
        if paren:
            aliases.append(paren.group(1))
        if re.search(r"[ぁ-ん].*[一-龥]|[一-龥].*[ぁ-ん]", line):
            aliases.append(SPACE_RE.sub("", line))
    return aliases


def match_person_in_district(
    mic_name: str,
    mic_raw: str,
    district_people: list[tuple[str, str]],
    kana_by_person: dict[str, set[str]],
) -> str | None:
    if not district_people:
        return None
    mic_n = normalize_name(mic_name)
    mic_s = normalize_name_soft(mic_name)
    raw_aliases = [normalize_name(a) for a in extract_raw_aliases(mic_raw)]
    raw_kana = {kana_compact(a) for a in raw_aliases + [mic_name, mic_raw]}
    raw_kana.discard("")

    exact = [pid for pid, nm in district_people if normalize_name(nm) == mic_n]
    if len(exact) == 1:
        return exact[0]

    soft = [pid for pid, nm in district_people if normalize_name_soft(nm) == mic_s and mic_s]
    if len(soft) == 1:
        return soft[0]

    if mic_s and len(mic_s) >= 2:
        suf = [pid for pid, nm in district_people if normalize_name_soft(nm).endswith(mic_s)]
        if len(set(suf)) == 1:
            return suf[0]

    hit = [pid for pid, nm in district_people if normalize_name(nm) in raw_aliases]
    if len(set(hit)) == 1:
        return hit[0]

    kana_hit = []
    for pid, _nm in district_people:
        person_kana = kana_by_person.get(pid) or set()
        if person_kana & raw_kana:
            kana_hit.append(pid)
        for pk in person_kana:
            if pk and pk in mic_n:
                kana_hit.append(pid)
    if len(set(kana_hit)) == 1:
        return kana_hit[0]
    return None


def load_mic_smd_names() -> list[tuple[int, str, int, str, str]]:
    if not FACTS.is_file():
        return []
    con = duckdb.connect()
    rows = con.execute(
        f"""
        SELECT election_kaiji, prefecture, district_number,
               CAST(candidate AS VARCHAR), CAST(candidate_raw AS VARCHAR)
        FROM read_parquet('{FACTS.as_posix()}')
        WHERE election_id LIKE 'shugiin-%'
          AND metric = 'candidate_votes' AND contest = 'smd'
          AND candidate IS NOT NULL
        """
    ).fetchall()
    return [(int(a), str(b), int(c), str(d or ""), str(e or "")) for a, b, c, d, e in rows]


def main() -> None:
    if not YOMI_CSV.is_file():
        raise SystemExit(f"missing {YOMI_CSV}")

    kokkai = load_kokkai()
    kokkai_by_name = kokkai_name_index(kokkai)
    canonical, yomi_rows, district_cands = load_yomi(kokkai_by_name)
    for pid, kanji, _kana in kokkai:
        if kanji:
            canonical[pid] = kanji

    mic_rows = load_mic_smd_names()
    kana_by_person: dict[str, set[str]] = defaultdict(set)
    for pid, _kanji, kana in kokkai:
        if not kana:
            continue
        kana_by_person[pid].add(normalize_name(kana))
        kana_by_person[pid].add(SPACE_RE.sub("", kana))
        family = kana.split()[0] if kana.split() else ""
        if family:
            kana_by_person[pid].add(normalize_name(family))

    bucket: dict[tuple[str, str], dict] = {}

    for r in yomi_rows:
        pid = r["person_id"]
        if not pid:
            continue
        name_ids = kokkai_by_name.get(normalize_name(r["name"])) or set()
        if len(name_ids) == 1 and next(iter(name_ids)) != pid:
            continue
        canon = canonical.get(pid) or r["name"]
        add_alias(bucket, pid, r["name"], "yomi_print", canon)
        add_alias(bucket, pid, canon, "yomi_canonical", canon)

    for pid, kanji, kana in kokkai:
        canon = canonical.get(pid) or kanji
        if kanji:
            add_alias(bucket, pid, kanji, "kokkai", canon)
        if kana:
            add_alias(bucket, pid, kana, "kokkai_kana", canon)
            add_alias(bucket, pid, SPACE_RE.sub("", kana), "kokkai_kana", canon)
            family = kana.split()[0] if kana.split() else kana
            add_alias(bucket, pid, family, "kokkai_kana_family", canon)

    linked = 0
    for kaiji, pref, dist, cand, raw in mic_rows:
        people = district_cands.get((kaiji, pref, dist)) or []
        pid = match_person_in_district(cand, raw, people, kana_by_person)
        if not pid:
            continue
        name_ids = kokkai_by_name.get(normalize_name(cand)) or set()
        if len(name_ids) == 1 and next(iter(name_ids)) != pid:
            continue
        canon = canonical.get(pid) or cand
        add_alias(bucket, pid, cand, "mic_smd", canon)
        for a in extract_raw_aliases(raw):
            n = normalize_name(a)
            if len(n) < 2 or n.startswith("(") or n.startswith("（"):
                continue
            other = kokkai_by_name.get(n) or set()
            if len(other) == 1 and next(iter(other)) != pid:
                continue
            add_alias(bucket, pid, a, "mic_raw", canon)
        linked += 1

    rows = list(bucket.values())
    rows.sort(key=lambda r: (r["person_id"], r["alias_name"]))

    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamped = OUT_DIR / f"{stamp}_person_name_aliases.jsonl"
    latest = OUT_DIR / "person_name_aliases.jsonl"
    with stamped.open("w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    latest.write_text(stamped.read_text(encoding="utf-8"), encoding="utf-8")

    WEB_OUT.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(
        f"""
        COPY (
          SELECT * FROM read_json_auto('{stamped.as_posix()}')
          ORDER BY person_id, alias_name
        ) TO '{WEB_OUT.as_posix()}' (FORMAT PARQUET)
        """
    )

    verify_osa = [r for r in rows if r["person_id"] == "r02606"]
    verify_abe = [r for r in rows if r["person_id"] == "r02187"]
    verify_hayashi = [r for r in rows if r["person_id"] == "r03160"]
    report = OUT_DIR / f"{stamp}_alias_build_report.txt"
    lines = [
        f"persons={len(canonical)} alias_rows={len(rows)} mic_district_links={linked} "
        f"yomi_giin_corrections={_LAST_YOMI_CORRECTIONS}",
        f"yomi_csv={YOMI_CSV}",
        f"web_out={WEB_OUT}",
        "",
        "VERIFY r02606 逢坂誠二 aliases:",
    ]
    for r in sorted(verify_osa, key=lambda x: x["alias_name"]):
        lines.append(f"  - {r['alias_name']!r} norm={r['alias_normalized']!r} src={r['source']}")
    lines += ["", "VERIFY r02187 安倍晋三 must NOT include 林芳正:"]
    for r in sorted(verify_abe, key=lambda x: x["alias_name"]):
        lines.append(f"  - {r['alias_name']!r} canon={r['canonical_name']!r} src={r['source']}")
    lines += ["", "VERIFY r03160 林芳正:"]
    for r in sorted(verify_hayashi, key=lambda x: x["alias_name"]):
        lines.append(f"  - {r['alias_name']!r} canon={r['canonical_name']!r} src={r['source']}")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"wrote {stamped}")
    print(f"wrote {WEB_OUT}")


if __name__ == "__main__":
    main()
