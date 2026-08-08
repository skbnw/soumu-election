# v1.0: 北海道第5区周辺のExcel行をダンプ
from pathlib import Path
import xlrd

path = next(Path("data/shugiin48/raw").glob("03-13*"))
ws = xlrd.open_workbook(str(path)).sheet_by_index(0)
for r in list(range(0, 15)) + list(range(45, 60)):
    vals = [ws.cell_value(r, c) for c in range(20)]
    print(r, vals)
