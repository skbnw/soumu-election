"""Peek kaiji 48 Excel candidate layout patterns."""
import xlrd
from pathlib import Path

p = Path("data/shugiin48/raw/03-13_候補者別得票数_小選挙区_000516731.xls")
wb = xlrd.open_workbook(str(p))
sh = wb.sheet_by_index(0)
for r in range(0, 40):
    left = [sh.cell_value(r, c) for c in range(0, 10)]
    right = [sh.cell_value(r, c) for c in range(10, 20)]
    def fmt(vals):
        out = []
        for v in vals:
            if v == "" or v is None:
                out.append("")
            else:
                out.append(repr(v)[:30])
        return out
    print(f"{r:02d} L{fmt(left)}")
    print(f"   R{fmt(right)}")
