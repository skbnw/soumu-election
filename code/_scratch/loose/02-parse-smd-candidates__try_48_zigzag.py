# v1.0: Excelをページ相当セグメントに分割しzigzagパースを試す
import re
import sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from soumu_election.normalize import (
    base, candidate_name, compact, matrix, number, smd_candidate_offsets, smd_candidate_panel_starts,
)

import xlrd

path = next(Path("data/shugiin48/raw").glob("03-13*"))
wb = xlrd.open_workbook(str(path))
ws = wb.sheet_by_index(0)
table = [[ws.cell_value(r, c) for c in range(ws.ncols)] for r in range(ws.nrows)]

header_index = 1
header = list(table[header_index])
for column, value in enumerate(table[header_index + 1]):
    if compact(value) and column < len(header):
        header[column] = f"{header[column] or ''}{value or ''}"
starts = smd_candidate_panel_starts(header)
offsets_by_start = {s: smd_candidate_offsets(header, s) for s in starts}
status_map = {"新": "new", "前": "incumbent", "元": "former"}

# Split on note rows / big blank bands
segments = []
start_row = header_index + 2
for r in range(header_index + 2, len(table)):
    text = "".join(str(table[r][c] or "") for c in range(min(5, len(table[r]))))
    if text.startswith("(注)") or text.startswith("（注）"):
        if start_row < r:
            segments.append((start_row, r))
        # skip until blank after notes
        start_row = r + 1
while start_row < len(table) and not any(compact(v) for v in table[start_row]):
    start_row += 1
if start_row < len(table):
    # remaining: split further? for now one segment until end, but exclude trailing empties
    end = len(table)
    segments.append((start_row, end))

print("segments", segments[:10], "count", len(segments))

# Better: split every time BOTH panels show district headers on same row (page-like parallel start)
# PLUS initial segment and note boundaries
cut_points = {header_index + 2}
for r in range(header_index + 2, len(table)):
    labels = []
    for s in starts:
        lab = compact(table[r][s] if s < len(table[r]) else None)
        if re.fullmatch(r".+?[都道府県]第\d+区", lab):
            labels.append(lab)
    if len(labels) >= 2:
        cut_points.add(r)
    text = str(table[r][0] or "")
    if text.startswith("(注)") or text.startswith("（注）"):
        cut_points.add(r)
cut = sorted(cut_points)
segments = []
for i, a in enumerate(cut):
    b = cut[i + 1] if i + 1 < len(cut) else len(table)
    if b > a:
        segments.append((a, b))
print("cut segments", len(segments), segments[:15])

prefecture = None
district_number = None
facts = []
doc = {"election_kaiji": 48, "source_code": "03-13", "dataset": "x", "source_url": "", "source_file": path.name}
sheet = {"name": ws.name}

for seg_start, seg_end in segments:
    text0 = str(table[seg_start][0] or "") if seg_start < len(table) else ""
    if text0.startswith("(注)") or text0.startswith("（注）"):
        continue
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
            def cell(offset, _row=row, _start=start):
                if offset is None: return None
                idx = _start + offset
                return _row[idx] if idx < len(_row) else None
            chunks = [str(cell(offsets["name"]) or "")]
            name_col = start + offsets["name"]
            for look in (1, 2):
                peek = row_index + look
                if peek >= len(table) or name_col >= len(table[peek]):
                    break
                t = str(table[peek][name_col] or "")
                if "(" in t or "（" in t:
                    chunks.append(t); break
            name, raw = candidate_name("\n".join(chunks))
            votes = number(cell(offsets["votes"]))
            if not name or votes is None:
                continue
            facts.append({
                "prefecture": prefecture,
                "district_number": district_number,
                "candidate": name,
                "elected": label == "当",
                "value": votes,
                "party": compact(cell(offsets["party"])),
            })

by = defaultdict(list)
for f in facts:
    by[(f["prefecture"], f["district_number"])].append(f)
bad = sum(1 for k, rows in by.items() if sum(1 for r in rows if r["elected"]) != 1)
print("records", len(facts), "districts", len(by), "elected", sum(1 for f in facts if f["elected"]), "bad", bad)
print("has 池田真紀", any(f["candidate"]=="池田真紀" for f in facts))
print("hokkaido", sorted(d for p,d in by if p=="北海道"))
