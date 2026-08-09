"""
build_yomi_pr_meibo_from_articles.py v1.0 (soumu-election)

polidata_national_elections/scripts/build_yomi_hr_pr_block_meibo_silver.py v2.3 を継承。

変更メモ:
- v1.0: references/yomi_hirei_meibo_txt を Bronze 入力に変更
        出力を output/02-yomi-prlist と web/data 用 JSONL に変更
        print 比当クロスフィルは polidata 側 clean CSV を参照（あれば）

入力:
  references/yomi_hirei_meibo_txt/YYYY-MM-DD.txt
  補足: YYYY-<block>.txt（例: 2017-kyusyu.txt）

出力:
  output/02-yomi-prlist/YYYYMMDD_HHMM_pr_block_meibo.jsonl
  output/02-yomi-prlist/pr_block_meibo.jsonl（最新ポインタ）
  output/02-yomi-prlist/pr_block_party_summary.jsonl
  output/02-yomi-prlist/pr_block_meibo_crossfill_audit.jsonl
  output/02-yomi-prlist/YYYYMMDD_HHMM_pr_block_meibo_parse_report.txt
"""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BRONZE_DIR = REPO_ROOT / "references" / "yomi_hirei_meibo_txt"
SILVER_DIR = REPO_ROOT / "output" / "02-yomi-prlist"
POLIDATA_ROOT = Path(r"C:\Users\SKBNW\Documents\Github\polidata_national_elections")
LEGACY_WIN3 = SILVER_DIR / "pr_block_meibo_win3_legacy.jsonl"


def yomi_print_csv_path(repo_root=None):
    """比当補完用。soumu 内に無ければ polidata の clean/原本を参照。"""
    root = Path(repo_root) if repo_root is not None else REPO_ROOT
    candidates = [
        root / "references" / "yomi_print" / "yomi-election-data-1996-2026_clean.csv",
        POLIDATA_ROOT / "01-sources" / "yomi" / "02-silver" / "print" / "yomi-election-data-1996-2026_clean.csv",
        POLIDATA_ROOT / "01-sources" / "yomi" / "00-original" / "print" / "yomi-election-data-1996-2026.csv",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return candidates[0]

BLOCKS = [
    "北海道",
    "東北",
    "北関東",
    "南関東",
    "東京",
    "北陸信越",
    "東海",
    "近畿",
    "中国",
    "四国",
    "九州",
]
BLOCK_TO_NUM = {name: i + 1 for i, name in enumerate(BLOCKS)}
BLOCK_SET = set(BLOCKS)

YEAR_META = {
    "1996": ("1996-HR-41", 1996, 41),
    "2000": ("2000-HR-42", 2000, 42),
    "2003": ("2003-HR-43", 2003, 43),
    "2005": ("2005-HR-44", 2005, 44),
    "2009": ("2009-HR-45", 2009, 45),
    "2012": ("2012-HR-46", 2012, 46),
    "2014": ("2014-HR-47", 2014, 47),
    "2017": ("2017-HR-48", 2017, 48),
    "2021": ("2021-HR-49", 2021, 49),
    "2024": ("2024-HR-50", 2024, 50),
    "2026": ("2026-HR-51", 2026, 51),
}

# 記事に出る党派略称（誤検知防止のため許可リスト）
KNOWN_PARTIES = {
    "自民",
    "民主",
    "民主党",
    "共産",
    "社民",
    "公明",
    "維新",
    "国民",
    "立民",
    "立憲民",
    "立憲民主",
    "れいわ",
    "参政",
    "幸福",
    "みんな",
    "新進",
    "さきがけ",
    "自由",
    "保守",
    "無所属会",
    "新社会",
    "民改連",
    "自連合",
    "日本",
    "大地",
    "改革",
    "次世代",
    "希望",
    "生活",
    "みらい",
    "みんつく",
    "中道",
    "日本保守",
    "安楽会",
    "減ゆう",
    "コロナ新",
    "やまと",
    "日本第一",
    "Ｎ裁",
    "NHK",
    "こころ",
    "支持なし",
    "未来",
    "本質",
    "社会",
}

PARTY_CANON = {
    "立憲民": "立憲民主",
    "立憲民主": "立憲民主",
    "立民": "立民",
    "民主党": "民主",
    "民主": "民主",
    "自民": "自民",
    "共産": "共産",
    "社民": "社民",
    "公明": "公明",
    "維新": "維新",
    "国民": "国民",
    "れいわ": "れいわ",
    "参政": "参政",
    "Ｎ裁": "Ｎ党",
}

ZEN2HAN = str.maketrans(
    {
        **{chr(0xFF10 + i): str(i) for i in range(10)},
        "．": ".",
        "，": ",",
        "　": " ",
    }
)

TITLE_RE = re.compile(
    r"(?:第[０-９0-9]+回)?衆院(?:選|比例).{0,80}?"
    + r"("
    + "|".join(BLOCKS)
    + r")ブロック"
)

PARTY_HDR_PREFIX_RE = re.compile(r"^[　\s]*(?:◇|◆|■)(?P<body>.+)$")
PARTY_BRK_RE = re.compile(
    r"^[　\s]*《(?P<p>[^》]{1,20})》(?P<rest>.*)$"
)

# 正常: 獲得議席Ｎ　Ｘ，ＸＸＸ票 / 破損: 獲得議席ＸＸＸ，ＸＸＸ票（議席欠落）
# 2017確定: ７議席　Ｘ，ＸＸＸ票
SEATS_VOTES_RE = re.compile(
    r"獲得議席\s*([０-９0-9]+)\s+([０-９0-9，,]+)\s*票"
)
SEATS_GISEKI_RE = re.compile(r"([０-９0-9]+)\s*議席")
SEATS_ONLY_RE = re.compile(r"獲得議席\s*([０-９0-9]+)\s*(?:$|[^０-９0-9，,票])")
VOTES_MERGED_RE = re.compile(r"獲得議席\s*([０-９0-9，,]+)\s*票")
VOTES_RE = re.compile(r"([０-９0-9，,]+)\s*票")
PCT_RE = re.compile(r"[（(]\s*([０-９0-9．.]+)\s*％\s*[）)]")
MAX_PLAUSIBLE_SEATS = 40

# 〈６　　〉 のように数字前後に全角空白が入るケースあり
DHONDT_RE = re.compile(r"〈[　\s]*([０-９0-9]+)[　\s]*〉")

BLOCK_TEIIN_PATTERNS = [
    re.compile(r"［(?P<b>" + "|".join(BLOCKS) + r")］\s*＝\s*(?P<n>[０-９0-9]+)"),
    re.compile(r"■(?P<b>" + "|".join(BLOCKS) + r")\s*(?P<n>[０-９0-9]+)"),
    re.compile(r"◆(?P<b>" + "|".join(BLOCKS) + r")\s*(?P<n>[０-９0-9]+)"),
    re.compile(r"◇(?P<b>" + "|".join(BLOCKS) + r")\s*(?P<n>[０-９0-9]+)"),
    re.compile(r"〈(?P<b>" + "|".join(BLOCKS) + r")〉\s*(?P<n>[０-９0-9]+)"),
    re.compile(
        r"(?P<b>" + "|".join(BLOCKS) + r")\s*(?P<n>[０-９0-9]+)\s*[（(]"
    ),
]

PROFILE_RE = re.compile(
    # 横顔: 氏名（せい・めい）年齢… ／ 旧党籍（こ）などは対象外
    r"^[　\s]*◎?.{0,30}?[（(][ぁ-んァ-ヶー]+(?:[・･][ぁ-んァ-ヶー]+)+[）)]"
)
GUIDE_RE = re.compile(
    r"(開票結果の見方|候補者名の|ドント式|略歴は|四角囲み|丸囲み|"
    r"前回選挙以降|派閥名|復活当選|党派名の下|左から名簿)"
)

PREF_CHARS = (
    "北海|青森|岩手|宮城|秋田|山形|福島|茨城|栃木|群馬|埼玉|千葉|東京|神奈川|"
    "新潟|富山|石川|福井|山梨|長野|岐阜|静岡|愛知|三重|滋賀|京都|大阪|兵庫|"
    "奈良|和歌山|鳥取|島根|岡山|広島|山口|徳島|香川|愛媛|高知|福岡|佐賀|"
    "長崎|熊本|大分|宮崎|鹿児島|沖縄|奈良|和歌"
)


def z2h_num(s: str) -> str:
    return (s or "").translate(ZEN2HAN)


def parse_int_ja(s: str | None) -> int | None:
    if s is None:
        return None
    t = z2h_num(s).replace(",", "").replace(" ", "").strip()
    if not t:
        return None
    try:
        return int(float(t))
    except ValueError:
        return None


def parse_float_ja(s: str | None) -> float | None:
    if s is None:
        return None
    t = z2h_num(s).replace(",", "").replace(" ", "").strip()
    if not t:
        return None
    try:
        return float(t)
    except ValueError:
        return None


def normalize_party_token(raw: str) -> str:
    """『自　民』『立 憲 民』など紙面空白を潰して党派トークン化。"""
    p = re.sub(r"[　\s]+", "", (raw or "").strip())
    return p


def canon_party(raw: str) -> str:
    p = normalize_party_token(raw)
    return PARTY_CANON.get(p, p)


def is_known_party(raw: str) -> bool:
    p = normalize_party_token(raw)
    if p in BLOCK_SET:
        return False
    if p in KNOWN_PARTIES:
        return True
    return False


@dataclass
class PartyState:
    party: str
    seats_won: int | None = None
    votes: int | None = None
    vote_pct: float | None = None
    candidates: list[dict] = field(default_factory=list)


@dataclass
class BlockState:
    block: str
    teiin: int | None = None
    parties: list[PartyState] = field(default_factory=list)


def split_block_articles(text: str) -> list[tuple[str, str]]:
    """Return list of (block_name, article_body)."""
    matches = list(TITLE_RE.finditer(text))
    # Deduplicate consecutive same title positions; keep unique spans
    articles: list[tuple[str, str]] = []
    seen_spans: set[tuple[int, str]] = set()
    for i, m in enumerate(matches):
        # Skip matches that are guide sentences containing ブロック
        line_start = text.rfind("\n", 0, m.start()) + 1
        line_end = text.find("\n", m.end())
        if line_end < 0:
            line_end = len(text)
        line = text[line_start:line_end].strip()
        if GUIDE_RE.search(line):
            continue
        if not (
            "比例" in line
            or "衆院" in line
            or "最終" in line
            or "開票" in line
            or "確定" in line
        ):
            continue
        block = m.group(1)
        key = (m.start(), block)
        if key in seen_spans:
            continue
        # Prefer one article per block: if already have this block and this
        # looks like duplicate title, still keep (2000東北二重あり)
        seen_spans.add(key)
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        # End at next *valid* title: scan forward
        for j in range(i + 1, len(matches)):
            ls = text.rfind("\n", 0, matches[j].start()) + 1
            le = text.find("\n", matches[j].end())
            if le < 0:
                le = len(text)
            ln = text[ls:le].strip()
            if GUIDE_RE.search(ln):
                continue
            if not (
                "比例" in ln
                or "衆院" in ln
                or "最終" in ln
                or "開票" in ln
                or "確定" in ln
            ):
                continue
            end = matches[j].start()
            break
        body = text[m.start() : end]
        articles.append((block, body))
    # 同一ブロックの重複見出し（2000東北など）は長い方を採用
    merged: dict[str, str] = {}
    order: list[str] = []
    for block, body in articles:
        if block not in merged:
            merged[block] = body
            order.append(block)
            continue
        if len(body) > len(merged[block]):
            merged[block] = body
    return [(b, merged[b]) for b in order]


def extract_teiin(body: str, block: str) -> int | None:
    for pat in BLOCK_TEIIN_PATTERNS:
        for m in pat.finditer(body):
            if m.group("b") == block:
                n = parse_int_ja(m.group("n"))
                if n is not None:
                    return n
    return None


def try_party_header(line: str) -> tuple[str, str] | None:
    s = line.strip()
    if GUIDE_RE.search(s):
        return None

    raw = ""
    rest = ""
    m = PARTY_BRK_RE.match(s)
    if m:
        raw = normalize_party_token(m.group("p"))
        rest = m.group("rest") or ""
    else:
        m = PARTY_HDR_PREFIX_RE.match(s)
        if not m:
            return None
        body = m.group("body")
        if "獲得議席" in body:
            left, right = body.split("獲得議席", 1)
            raw = normalize_party_token(left)
            rest = "獲得議席" + right
        else:
            # 『自　民』『立憲民』など。先頭の党名トークンのみ。
            raw = normalize_party_token(body)
            rest = ""
            # 余分な注記が続く場合は既知党名の最長一致
            if raw not in KNOWN_PARTIES:
                for known in sorted(KNOWN_PARTIES, key=len, reverse=True):
                    if raw.startswith(known):
                        raw = known
                        break

    if not raw or raw in BLOCK_SET or raw.startswith("比例"):
        return None
    if any(x in s for x in ("囲み", "＝", "は前回", "は小選挙", "数字は", "派名")):
        if "獲得議席" not in s:
            return None
    if raw in KNOWN_PARTIES or "獲得議席" in rest or "獲得議席" in s:
        if len(raw) <= 1:
            return None
        if raw in {"本質"} and "獲得議席" not in s:
            return None
        return raw, rest
    return None


def update_party_metrics(party: PartyState, text: str) -> None:
    m = SEATS_VOTES_RE.search(text)
    if m:
        seats = parse_int_ja(m.group(1))
        votes = parse_int_ja(m.group(2))
        if seats is not None and seats <= MAX_PLAUSIBLE_SEATS:
            party.seats_won = seats
        if votes is not None:
            party.votes = votes
    else:
        m = VOTES_MERGED_RE.search(text)
        if m:
            # 『獲得議席１２６７，１４５票』= 議席欠落・得票のみ
            raw = m.group(1)
            if "，" in raw or "," in raw or (parse_int_ja(raw) or 0) > MAX_PLAUSIBLE_SEATS:
                party.votes = parse_int_ja(raw)
            else:
                seats = parse_int_ja(raw)
                if seats is not None and seats <= MAX_PLAUSIBLE_SEATS:
                    party.seats_won = seats
        else:
            m = SEATS_ONLY_RE.search(text)
            if m:
                seats = parse_int_ja(m.group(1))
                if seats is not None and seats <= MAX_PLAUSIBLE_SEATS:
                    party.seats_won = seats
            m = SEATS_GISEKI_RE.search(text)
            if m and party.seats_won is None:
                seats = parse_int_ja(m.group(1))
                if seats is not None and seats <= MAX_PLAUSIBLE_SEATS:
                    party.seats_won = seats
            m = VOTES_RE.search(text)
            if m and party.votes is None:
                party.votes = parse_int_ja(m.group(1))

    # 異常値の清掃
    if party.seats_won is not None and party.seats_won > MAX_PLAUSIBLE_SEATS:
        party.seats_won = None

    m = PCT_RE.search(text)
    if m:
        party.vote_pct = parse_float_ja(m.group(1))


def is_profile_line(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    if PROFILE_RE.match(s):
        return True
    if s.startswith("◎"):
        return True
    # 略歴ブロックの番号付き行
    if re.match(r"^[　\s]*〈[１２３４1-4]〉", s) and any(
        k in s for k in ("党", "大臣", "議員", "大", "高", "中学", "市", "町")
    ):
        return True
    return False


def parse_candidate_line(
    line: str, prev_rank: int | None
) -> tuple[dict | None, int | None]:
    """Parse one candidate row. Returns (row|None, new_prev_rank)."""
    raw = line.rstrip("\n")
    s = raw.strip()
    if not s:
        return None, prev_rank
    if GUIDE_RE.search(s):
        return None, prev_rank
    if is_profile_line(s):
        return None, prev_rank
    # 票数のみ・獲得議席のみ
    if "獲得議席" in s and not re.search(r"(当|小当)", s):
        return None, prev_rank
    if re.match(r"^[　\s]*[０-９0-9，,]+\s*票", s):
        return None, prev_rank

    work = s
    # skip leading markers
    work = re.sub(r"^[　\s]+", "", work)

    meibo_rank: int | None = None
    ditto = False
    if work.startswith("〃"):
        ditto = True
        work = work[1:].lstrip(" 　")
    else:
        m = re.match(r"^([０-９0-9]+)(?![０-９0-9票％])", work)
        if m:
            meibo_rank = parse_int_ja(m.group(1))
            work = work[m.end() :].lstrip(" 　")

    d_hondt: int | None = None
    m = DHONDT_RE.match(work)
    if m:
        d_hondt = parse_int_ja(m.group(1))
        work = work[m.end() :].lstrip(" 　")

    status = ""
    if work.startswith("〈小当〉"):
        status = "小当"
        work = work[len("〈小当〉") :].lstrip(" 　")
    elif work.startswith("小当"):
        status = "小当"
        work = work[2:].lstrip(" 　")
    elif re.match(r"^当(?![選落])", work):
        status = "当"
        work = work[1:].lstrip(" 　")

    if not work:
        return None, prev_rank
    if not re.search(r"[一-龥ぁ-んァ-ヶ]", work):
        return None, prev_rank
    if "である" in work or "という" in work:
        return None, prev_rank

    if ditto or meibo_rank is None:
        meibo_rank = prev_rank
    if meibo_rank is None:
        if status not in {"当", "小当"} and d_hondt is None:
            return None, prev_rank

    sekihairitsu: float | None = None
    m = re.search(r"([０-９0-9]{1,3}[．.][０-９0-9]{2,3})\s*$", work)
    if m:
        sekihairitsu = parse_float_ja(m.group(1))
        work = work[: m.start()].rstrip(" 　")

    dual_district = ""
    m = re.search(r"＜([^＞]+)＞\s*$", work)
    if m:
        dual_district = m.group(1).strip()
        work = work[: m.start()].rstrip(" 　")
    else:
        m = re.search(
            r"〈[　\s]*(単独|(?:" + PREF_CHARS + r")[０-９0-9]*)[　\s]*〉", work
        )
        if m:
            dual_district = re.sub(r"[　\s]+", "", m.group(1))
            work = (work[: m.start()] + work[m.end() :]).strip(" 　")
        else:
            m = re.search(
                r"(?:^|[　\s])(単独|(?:"
                + PREF_CHARS
                + r")[０-９0-9]*)(?=[　\s前新元（(]|$)",
                work,
            )
            if m:
                dual_district = m.group(1)
                start = m.start(1)
                end = m.end(1)
                work = (work[:start] + work[end:]).strip(" 　")

    terms: int | None = None
    m = re.search(r"《\s*([０-９0-9]+)\s*》", work)
    if m:
        terms = parse_int_ja(m.group(1))
        work = (work[: m.start()] + work[m.end() :]).strip(" 　")
        if not dual_district:
            m2 = re.search(
                r"(?:^|[　\s])(単独|(?:"
                + PREF_CHARS
                + r")[０-９0-9]*)(?=[　\s前新元（(]|$)",
                work,
            )
            if m2:
                dual_district = m2.group(1)
                work = (work[: m2.start(1)] + work[m2.end(1) :]).strip(" 　")

    faction = ""
    m = re.search(r"〈([^〉]{1,4})〉", work)
    if m:
        inner = re.sub(r"[　\s]+", "", m.group(1))
        if inner not in {"小当"} and not re.search(
            r"(?:" + PREF_CHARS + r")|[０-９0-9]", inner
        ):
            faction = inner
            work = (work[: m.start()] + work[m.end() :]).strip(" 　")

    standing = ""
    m = re.search(r"[　\s]*(前|新|元)(?:[　\s]*[（(][^）)]+[）)])?\s*$", work)
    if m:
        standing = m.group(1)
        work = work[: m.start()].rstrip(" 　")

    work = work.replace("▽", "").strip(" 　")
    name = re.sub(r"[　\s]+", "", work)
    name = name.strip("・")
    name = name.replace("▽", "").replace("※", "")
    name = re.sub(r"[（(][^）)]{1,4}[）)]$", "", name)
    if not name or len(name) < 2:
        return None, prev_rank
    if name in KNOWN_PARTIES or name in BLOCK_SET:
        return None, prev_rank
    if any(x in name for x in ("獲得議席", "開票", "ブロック", "定数", "議席")):
        return None, prev_rank
    if "（" in name or "(" in name or "）" in name or ")" in name:
        return None, prev_rank
    if re.fullmatch(r"[ぁ-ん]+", name):
        return None, prev_rank

    row = {
        "meibo_rank": meibo_rank,
        "d_hondt_rank": d_hondt,
        "result_status": status,
        "candidate_name": name,
        "terms": terms,
        "dual_district": dual_district,
        "sekihairitsu": sekihairitsu,
        "faction": faction,
        "standing": standing,
        "is_elected_pr": status == "当",
        "is_elected_smd": status == "小当",
    }
    return row, meibo_rank if meibo_rank is not None else prev_rank


def parse_block_body(block: str, body: str) -> BlockState:
    st = BlockState(block=block, teiin=extract_teiin(body, block))
    current: PartyState | None = None
    prev_rank: int | None = None
    in_profile = False

    for line in body.splitlines():
        s = line.strip()
        if not s:
            continue

        # New party header resets profile mode
        ph = try_party_header(line)
        if ph:
            raw, rest = ph
            current = PartyState(party=canon_party(raw))
            update_party_metrics(current, s)
            update_party_metrics(current, rest)
            st.parties.append(current)
            prev_rank = None
            in_profile = False
            continue

        if current is None:
            # block-level teiin may appear before first party
            continue

        # metrics-only continuation under party
        if (
            "獲得議席" in s
            or "議席" in s
            or ("票" in s and "当" not in s and "小当" not in s)
        ):
            update_party_metrics(current, s)
            if not re.search(r"[一-龥]{2,}.*(?:当|小当|〈)", s):
                # pure metrics line
                if not re.search(r"^[　\s]*(?:[０-９0-9]+|〃)", s) and "当" not in s:
                    continue

        if is_profile_line(s):
            in_profile = True
            continue
        if in_profile:
            # stay in profile until blank already skipped; exit if candidate-like
            # number-led line
            if not re.match(r"^[　\s]*(?:[０-９0-9]+|〃|小当|〈小当〉|当)", s):
                continue
            in_profile = False

        cand, prev_rank = parse_candidate_line(line, prev_rank)
        if cand:
            current.candidates.append(cand)

    return st


def read_article_text(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "cp932"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("cp932", errors="replace")


def article_score(body: str) -> int:
    """同一ブロックに複数記事があるとき、確定稿を優先。"""
    head = "\n".join(body.splitlines()[:5])
    score = len(body)
    if "確定得票" in head or "確定得票" in body[:120]:
        score += 100_000
    if "最終結果" in head:
        score += 50_000
    if "当選者が決まっていません" in body:
        score -= 80_000
    # 粗い 当 行数
    score += body.count("　当　") * 20
    score += body.count("当　") * 5
    return score


def emit_block(
    *,
    election_id: str,
    year_i: int,
    th: int,
    block: str,
    body: str,
    source_file: str,
    rows: list[dict],
    party_rows: list[dict],
    warnings: list[str],
) -> None:
    bst = parse_block_body(block, body)
    block_num = BLOCK_TO_NUM[block]

    for pst in bst.parties:
        pr_n = sum(1 for c in pst.candidates if c["is_elected_pr"])
        if pst.seats_won is None and pr_n:
            pst.seats_won = pr_n
            pst.seats_inferred = True  # type: ignore[attr-defined]

    for pst in bst.parties:
        pr_n = sum(1 for c in pst.candidates if c["is_elected_pr"])
        party_rows.append(
            {
                "election_id": election_id,
                "year": year_i,
                "th": th,
                "pr_block_num": block_num,
                "pr_block_name": block,
                "party": pst.party,
                "party_key": pst.party,
                "seats_won": pst.seats_won,
                "seats_won_inferred": bool(getattr(pst, "seats_inferred", False)),
                "votes": pst.votes,
                "vote_pct": pst.vote_pct,
                "candidate_rows": len(pst.candidates),
                "elected_pr_count": pr_n,
                "source_file": source_file,
                "block_teiin": bst.teiin,
                "name_source": "yomi_print_article",
            }
        )
        for c in pst.candidates:
            rows.append(
                {
                    "election_id": election_id,
                    "year": year_i,
                    "th": th,
                    "pr_block_num": block_num,
                    "pr_block_name": block,
                    "party": pst.party,
                    "party_key": pst.party,
                    "party_seats_won": pst.seats_won,
                    "party_votes": pst.votes,
                    "party_vote_pct": pst.vote_pct,
                    "block_teiin": bst.teiin,
                    "meibo_rank": c["meibo_rank"],
                    "d_hondt_rank": c["d_hondt_rank"],
                    "candidate_name": c["candidate_name"],
                    "result_status": c["result_status"],
                    "is_elected_pr": c["is_elected_pr"],
                    "is_elected_smd": c["is_elected_smd"],
                    "is_elected": c["is_elected_pr"] or c["is_elected_smd"],
                    "terms": c["terms"],
                    "dual_district": c["dual_district"],
                    "sekihairitsu": c["sekihairitsu"],
                    "faction": c["faction"],
                    "standing": c["standing"],
                    "name_source": "yomi_print_article",
                    "roster_kind": "hirei_kiji_meibo",
                    "source_file": source_file,
                }
            )

    pr_won = sum(
        1 for pst in bst.parties for c in pst.candidates if c["is_elected_pr"]
    )
    declared = sum(pst.seats_won or 0 for pst in bst.parties if pst.seats_won is not None)
    if bst.teiin is not None and pr_won and abs(pr_won - bst.teiin) > 1:
        warnings.append(f"{election_id} {block}: teiin={bst.teiin} but 当={pr_won}")
    if declared and pr_won and abs(declared - pr_won) > 1:
        warnings.append(
            f"{election_id} {block}: party_seats_sum={declared} but 当={pr_won}"
        )


def parse_year_files(year: str, paths: list[Path]) -> tuple[list[dict], list[dict], list[str]]:
    election_id, year_i, th = YEAR_META[year]
    warnings: list[str] = []
    rows: list[dict] = []
    party_rows: list[dict] = []

    # block -> (score, body, source)
    best: dict[str, tuple[int, str, str]] = {}
    for path in paths:
        text = read_article_text(path)
        articles = split_block_articles(text)
        if not articles:
            warnings.append(f"{path.name}: no block titles detected")
            continue
        for block, body in articles:
            score = article_score(body)
            prev = best.get(block)
            if prev is None or score > prev[0]:
                best[block] = (score, body, path.name)

    missing = [b for b in BLOCKS if b not in best]
    if missing:
        warnings.append(f"{year}: missing blocks {missing}")

    for block in BLOCKS:
        if block not in best:
            continue
        _, body, source_file = best[block]
        emit_block(
            election_id=election_id,
            year_i=year_i,
            th=th,
            block=block,
            body=body,
            source_file=source_file,
            rows=rows,
            party_rows=party_rows,
            warnings=warnings,
        )
    return rows, party_rows, warnings


def list_bronze_by_year() -> dict[str, list[Path]]:
    by_year: dict[str, list[Path]] = defaultdict(list)
    for path in sorted(BRONZE_DIR.glob("*.txt")):
        year = path.stem[:4]
        if year in YEAR_META:
            by_year[year].append(path)
    return by_year


def norm_person_name(name: str) -> str:
    return re.sub(r"[\s　]+", "", name or "")


def load_print_hitou_index() -> dict[tuple[int, int], set[str]]:
    """(year, pr_block_num) -> 比当候補者名（空白除去）."""
    csv_path = yomi_print_csv_path(REPO_ROOT)
    if not csv_path.is_file():
        return {}
    out: dict[tuple[int, int], set[str]] = defaultdict(set)
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if (row.get("当落") or "").strip() != "比当":
                continue
            try:
                year = int(float(str(row.get("year") or "").strip()))
                block = int(float(str(row.get("block_num") or "").strip()))
            except ValueError:
                continue
            nm = norm_person_name(row.get("candidate_name") or "")
            if nm:
                out[(year, block)].add(nm)
    return out


def apply_print_hitou_crossfill(
    rows: list[dict], party_rows: list[dict]
) -> list[dict]:
    """
    記事本文で「当」印が欠落した比例当選を、print clean CSV の比当で補完する。
    """
    hitou = load_print_hitou_index()
    audit: list[dict] = []
    if not hitou:
        return audit

    for r in rows:
        if r.get("is_elected_pr"):
            continue
        key = (int(r["year"]), int(r["pr_block_num"]))
        nm = norm_person_name(r.get("candidate_name") or "")
        if nm not in hitou.get(key, set()):
            continue
        before = r.get("result_status") or ""
        r["result_status"] = "当"
        r["is_elected_pr"] = True
        r["is_elected"] = True
        r["status_source"] = "print_hitou_crossfill"
        audit.append(
            {
                "election_id": r["election_id"],
                "pr_block_name": r["pr_block_name"],
                "party": r["party"],
                "candidate_name": r["candidate_name"],
                "before_status": before,
                "after_status": "当",
                "source": "print_clean_csv:当落=比当",
            }
        )

    # party summary の当選数を再集計
    tou_by: dict[tuple[str, str, str], int] = defaultdict(int)
    for r in rows:
        if r.get("is_elected_pr"):
            tou_by[(r["election_id"], r["pr_block_name"], r["party"])] += 1
    for pr in party_rows:
        key = (pr["election_id"], pr["pr_block_name"], pr["party"])
        pr["elected_pr_count"] = tou_by.get(key, 0)

    return audit


def archive_legacy_win3() -> None:
    old = SILVER_DIR / "pr_block_meibo.jsonl"
    if not old.is_file():
        return
    # only archive if looks like win3 legacy
    head = old.read_text(encoding="utf-8", errors="replace")[:200]
    if "hirei_roster_win3" in head or "win_flag" in head:
        if not LEGACY_WIN3.exists():
            LEGACY_WIN3.write_text(old.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"Archived legacy win3 -> {LEGACY_WIN3}")


def write_report(
    rows: list[dict],
    party_rows: list[dict],
    warnings: list[str],
    report_path: Path,
    crossfill_n: int = 0,
) -> None:
    by_eid: dict[str, int] = defaultdict(int)
    by_eid_pr: dict[str, int] = defaultdict(int)
    blocks: dict[str, set[str]] = defaultdict(set)
    sources: dict[str, set[str]] = defaultdict(set)
    for r in rows:
        by_eid[r["election_id"]] += 1
        if r["is_elected_pr"]:
            by_eid_pr[r["election_id"]] += 1
        blocks[r["election_id"]].add(r["pr_block_name"])
        sources[r["election_id"]].add(r["source_file"])

    expected_tou = {
        "1996-HR-41": 200,
        "2000-HR-42": 180,
        "2003-HR-43": 180,
        "2005-HR-44": 180,
        "2009-HR-45": 180,
        "2012-HR-46": 180,
        "2014-HR-47": 180,
        "2017-HR-48": 176,
        "2021-HR-49": 176,
        "2024-HR-50": 176,
        "2026-HR-51": 176,
    }

    lines = [
        "読売 比例名簿 クリーン正本 パース報告",
        f"generated_at: {datetime.now().isoformat(timespec='seconds')}",
        f"candidate_rows: {len(rows)}",
        f"party_rows: {len(party_rows)}",
        f"print_hitou_crossfill: {crossfill_n}",
        "",
        "BY ELECTION",
    ]
    for eid in sorted(by_eid):
        exp = expected_tou.get(eid)
        tou = by_eid_pr[eid]
        gap = ""
        if exp is not None:
            gap = f" expected={exp} diff={tou - exp:+d}"
        lines.append(
            f"  {eid}: candidates={by_eid[eid]} 当={tou} "
            f"blocks={len(blocks[eid])}/11 sources={sorted(sources[eid])}{gap}"
        )
    lines.append("")
    lines.append(f"WARNINGS ({len(warnings)})")
    for w in warnings[:200]:
        lines.append(f"  - {w}")
    if len(warnings) > 200:
        lines.append(f"  ... +{len(warnings) - 200}")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(report_path.read_text(encoding="utf-8"))


def main() -> None:
    SILVER_DIR.mkdir(parents=True, exist_ok=True)
    archive_legacy_win3()

    by_year = list_bronze_by_year()
    if not by_year:
        raise SystemExit(f"no article files in {BRONZE_DIR}")

    all_rows: list[dict] = []
    all_parties: list[dict] = []
    all_warnings: list[str] = []
    for year in sorted(by_year):
        rows, parties, warnings = parse_year_files(year, by_year[year])
        all_rows.extend(rows)
        all_parties.extend(parties)
        all_warnings.extend(warnings)
        print(
            f"parsed {year}: files={[p.name for p in by_year[year]]} "
            f"candidates={len(rows)} parties={len(parties)}"
        )

    # クリーン正本化: print 比当で記事の「当」欠落を補完
    audit = apply_print_hitou_crossfill(all_rows, all_parties)
    print(f"print_hitou_crossfill applied: {len(audit)}")
    for a in audit:
        print(
            f"  + {a['election_id']} {a['pr_block_name']} "
            f"{a['party']} {a['candidate_name']}"
        )

    all_rows.sort(
        key=lambda x: (
            x["election_id"],
            x["pr_block_num"],
            x["party"],
            x["meibo_rank"] if x["meibo_rank"] is not None else 9999,
            x["d_hondt_rank"] if x["d_hondt_rank"] is not None else 9999,
            x["candidate_name"],
        )
    )
    all_parties.sort(
        key=lambda x: (x["election_id"], x["pr_block_num"], x["party"])
    )

    out_meibo = SILVER_DIR / "pr_block_meibo.jsonl"
    out_party = SILVER_DIR / "pr_block_party_summary.jsonl"
    out_audit = SILVER_DIR / "pr_block_meibo_crossfill_audit.jsonl"
    with out_meibo.open("w", encoding="utf-8", newline="\n") as f:
        for r in all_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with out_party.open("w", encoding="utf-8", newline="\n") as f:
        for r in all_parties:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with out_audit.open("w", encoding="utf-8", newline="\n") as f:
        for r in audit:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    report = SILVER_DIR / f"{stamp}_pr_block_meibo_parse_report.txt"
    report.parent.mkdir(parents=True, exist_ok=True)
    write_report(all_rows, all_parties, all_warnings, report, crossfill_n=len(audit))
    stamped = SILVER_DIR / f"{stamp}_pr_block_meibo.jsonl"
    stamped.write_text(out_meibo.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"Wrote {out_meibo} rows={len(all_rows)}")
    print(f"Wrote {stamped}")
    print(f"Wrote {out_party} rows={len(all_parties)}")
    print(f"Wrote {out_audit} rows={len(audit)}")


if __name__ == "__main__":
    main()
