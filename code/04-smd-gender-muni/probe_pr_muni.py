# v1.0: 市区町村Excelに有権者列や比例レイアウトがあるか確認
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from soumu_election.download import parse_smd, parse_pr, workbook_tables, clean_text

smd = next(Path("data/shugiin51/raw").glob("03-14-smd-15*"))  # tokyo
print("=== SMD Tokyo sheet headers sample ===")
for name, table in list(workbook_tables(smd))[:1]:
    print("sheet", name)
    for i, row in enumerate(table[:12]):
        print(i, [clean_text(c) for c in row[:8]])

pr = next(Path("data/shugiin51/raw").glob("03-14-pr-05*"))  # tokyo block?
print("\n=== PR file", pr.name)
recs = parse_pr(pr, {"label": "東京都", "url": "", "category": "pr"}, 51)
print("pr records", len(recs))
print("sample", recs[0] if recs else None)
print("units", sorted({r["reporting_unit"] for r in recs})[:15])
print("row_types", sorted({r["row_type"] for r in recs}))

# older kaiji with 47 pr files (per prefecture)
pr45 = next(Path("data/shugiin45/raw").glob("03-14-pr-01*"))
print("\n=== PR45", pr45.name)
recs45 = parse_pr(pr45, {"label": "北海道", "url": "", "category": "pr"}, 45)
print("records", len(recs45), "sample", recs45[0] if recs45 else None)
