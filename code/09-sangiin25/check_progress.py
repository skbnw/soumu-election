#!/usr/bin/env python3
from pathlib import Path
import json
import os

paths = [
    Path("web/data/meta.json"),
    Path("web/data/facts.parquet"),
    Path("web/data/municipality_facts.parquet"),
    Path("data/sangiin25/normalized/facts.json"),
    Path("data/sangiin25/manifest.json"),
]
for p in paths:
    if p.exists():
        st = p.stat()
        print(p, st.st_size, st.st_mtime)
    else:
        print(p, "MISSING")

if Path("web/data/meta.json").exists():
    print(json.loads(Path("web/data/meta.json").read_text(encoding="utf-8")))

# list python-ish pids via tasklist
os.system('tasklist /FI "IMAGENAME eq python.exe"')
