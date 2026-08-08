# v1.0: displayPersonName 修正後の表示サンプル確認（JSロジック相当）
import re

def strip_spaces(value):
    return re.sub(r"[\s\u3000]+", "", str(value or ""))

def is_mostly_kana(value):
    chars = [ch for ch in value if not re.match(r"[\s\u3000]", ch)]
    if not chars:
        return False
    kana = sum(1 for ch in chars if "\u3040" <= ch <= "\u309F" or "\u30A0" <= ch <= "\u30FF" or ch == "ー")
    return kana / len(chars) >= 0.7

def display_person_name(name, raw):
    compact = strip_spaces(name)
    if not raw:
        return compact or "—"
    text = str(raw)
    lines = [ln.strip() for ln in re.split(r"\r?\n", text) if ln.strip()]
    paren = re.search(r"[（(]\s*([^）)]+?)\s*[）)]", text)
    kanji = compact or (strip_spaces(paren.group(1)) if paren else "")
    reading_lines = [strip_spaces(ln) for ln in lines if not re.search(r"[（(]", ln)]
    reading_lines = [ln for ln in reading_lines if ln]

    def score(value):
        kana = sum(1 for ch in value if "\u3040" <= ch <= "\u309F" or "\u30A0" <= ch <= "\u30FF" or ch == "ー")
        return len(value) * 10 + kana

    kana_cands = [ln for ln in reading_lines if is_mostly_kana(ln)]
    pool = kana_cands or reading_lines
    reading = sorted(pool, key=score, reverse=True)[0] if pool else ""
    if reading and kanji and reading != kanji:
        if len(reading) <= 1 and len(kanji) >= 2:
            return kanji
        return f"{reading}（{kanji}）"
    return kanji or reading or "—"

samples = [
    ("円子裕子", "こ\nまるこ ゆう子\n(円 子 裕 子)"),
    ("三反園訓", "みたぞの さ と し\n(三 反 園 訓)"),
    ("階猛", "しな たけし\n(階 猛)"),
    ("辻恵", "めぐむ\nつじ 恵\n(辻 恵)"),
    ("前久", "まえ\n前 ひさし\n(前 久)"),
    ("馳浩", "ひろし\nはせ 浩\n(馳 浩)"),
    ("堀讓", "堀　　ゆずる\n(堀　　讓)"),
]
for name, raw in samples:
    print(repr(raw.replace("\n", " | ")), "=>", display_person_name(name, raw))
