#!/usr/bin/env python3
from pathlib import Path
import time
p = Path("web/data/municipality_facts.parquet")
print("size", p.stat().st_size, "mtime", time.ctime(p.stat().st_mtime))
# also warehouse copy
w = Path("data/warehouse/parquet/municipality_facts.parquet")
print("wh size", w.stat().st_size if w.exists() else None, "mtime", time.ctime(w.stat().st_mtime) if w.exists() else None)
