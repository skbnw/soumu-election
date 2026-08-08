# peek 03-07 / 03-05 / 03-10 excel structure for kaiji 50
from pathlib import Path
import xlrd
from openpyxl import load_workbook

DATA = Path(r"C:\Users\SKBNW\Documents\Github\soumu-election\data\shugiin50\raw")

def peek_xls(path, max_rows=40):
    print(f"\n### {path.name}")
    book = xlrd.open_workbook(path)
    sheet = book.sheet_by_index(0)
    print(f"rows={sheet.nrows} cols={sheet.ncols}")
    for r in range(min(max_rows, sheet.nrows)):
        vals = [sheet.cell_value(r, c) for c in range(min(16, sheet.ncols))]
        if any(str(v).strip() for v in vals):
            print(f"R{r}: {vals}")

for pat in ["03-07*", "03-05*", "03-10*"]:
    paths = list(DATA.glob(pat))
    if paths:
        peek_xls(paths[0], 35 if "07" in pat else 25)
