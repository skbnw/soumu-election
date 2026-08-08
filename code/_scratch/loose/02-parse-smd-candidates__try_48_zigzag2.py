# v1.1: 注記行だけでセグメント分割し zigzag（左列→右列）でパース
import re
import sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from soumu_election.normalize import candidate_name, compact, number, smd_candidate_offsets, smd_candidate_panel_starts
import xlrd

path = next(Path("data/shugiin48/raw").glob("03-13*"))
ws = xlrd.open_workbook(str(path)).sheet_by_index(0)
table = [[ws.cell_value(r, c) for c in range(ws.ncols)] for r in range(ws.nrows)]
header_index = 1
header = list(table[header_index])
for column, value in enumerate(table[header_index + 1]):
    if compact(value) and column < len(header):
        header[column] = f"{header[column] or ''}{value or ''}"
starts = smd_candidate_panel_starts(header)
offsets_by_start = {s: smd_candidate_offsets(header, s) for s in starts}

# page-like segments from note markers only
bounds = [header_index + 2]
for r in range(header_index + 2, len(table)):
    text = str(table[r][0] or "")
    if text.startswith("(注)") or text.startswith("（注）"):
        bounds.append(r)
bounds.append(len(table))
segments = []
for i in range(len(bounds) - 1):
    a, b = bounds[i], bounds[i + 1]
    # skip pure note blocks
    if str(table[a][0] or "").startswith("(注)") or str(table[a][0] or "").startswith("（注）"):
        # advance to first non-note/non-empty
        r = a
        while r < b and (str(table[r][0] or "").startswith("(注)") or str(table[r][0] or "").startswith("（注）") or str(table[r][0] or "").startswith(" ") or not any(compact(v) for v in table[r][:12])):
            r += 1
        a = r
    if a < b:
        segments.append((a, b))
print("segments", len(segments), segments[:5], "...", segments[-2:])

prefecture = district_number = None
facts = []
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
            def cell(offset, _row=row, _start=start):
                if offset is None: return None
                idx = _start + offset
                return _row[idx] if idx < len(_row) else None
            chunks = [str(cell(offsets["name"]) or "")]
            name_col = start + offsets["name"]
            for look in (1, 2):
                peek = row_index + look
                if peek >= len(table) or name_col >= len(table[peek]): break
                t = str(table[peek][name_col] or "")
                if "(" in t or "（" in t:
                    chunks.append(t); break
            name, raw = candidate_name("\n".join(chunks))
            votes = number(cell(offsets["votes"]))
            if not name or votes is None: continue
            facts.append({"prefecture": prefecture, "district_number": district_number, "candidate": name, "elected": label=="当", "value": votes})

by = defaultdict(list)
for f in facts:
    by[(f["prefecture"], f["district_number"])].append(f)
bad = sum(1 for k, rows in by.items() if sum(1 for r in rows if r["elected"]) != 1)
print("records", len(facts), "districts", len(by), "elected", sum(1 for f in facts if f["elected"]), "bad", bad)
print("has 池田真紀", any(f["candidate"]=="池田真紀" for f in facts))
ikeda = [f for f in facts if f["candidate"]=="池田真紀"][0]
print("池田", ikeda)
print("hokkaido", sorted(d for p,d in by if p=="北海道"))
