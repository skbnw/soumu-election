# v1.0: 第48回 Excel の選挙区ヘッダ出現箇所を列挙
from pathlib import Path
import xlrd
import re

path = next(Path("data/shugiin48/raw").glob("03-13*"))
wb = xlrd.open_workbook(str(path))
ws = wb.sheet_by_index(0)
pat = re.compile(r"第\d+区")
for r in range(ws.nrows):
    for c in range(min(ws.ncols, 20)):
        v = ws.cell_value(r, c)
        if isinstance(v, str) and pat.search(v.replace(" ", "").replace("\u3000", "")):
            print(r, c, repr(v))
