# v1.0: 市区町村別Excelのパース可否と件数を確認
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

# download.parse_smd imports requests at module level — import only needed pieces via exec? 
# Install requests if missing, or duplicate minimal parse.

try:
    import requests  # noqa: F401
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "beautifulsoup4", "openpyxl", "-q"])

from soumu_election.download import parse_smd

path = next(Path("data/shugiin51/raw").glob("03-14-smd-01*"))
source = {"label": "北海道", "url": "", "category": "smd"}
recs = parse_smd(path, source, 51)
print("file", path.name, "records", len(recs))
print("sample", recs[0])
print("row_types", sorted({r["row_type"] for r in recs}))
print("districts sample", sorted({r["district"] for r in recs})[:5])
units = [r for r in recs if r["row_type"] == "reporting_unit"]
print("reporting_unit rows", len(units), "sample unit", units[0]["reporting_unit"] if units else None)
# gender?
print("keys", recs[0].keys())
