from pathlib import Path
import xlrd
path = next(Path(r"C:\Users\SKBNW\Documents\Github\soumu-election\data\shugiin50\raw").glob("03-07*"))
book = xlrd.open_workbook(path)
s = book.sheet_by_index(0)
for r in range(60, 80):
    print(r, [s.cell_value(r,c) for c in range(min(8,s.ncols))])
