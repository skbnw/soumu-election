import json
from pathlib import Path
m = json.loads(Path(r"C:\Users\SKBNW\Documents\Github\soumu-election\data\shugiin51\manifest.json").read_text(encoding="utf-8"))
for s in m["sources"]:
    if str(s.get("source_code","")).startswith("03-11"):
        print(json.dumps(s, ensure_ascii=False, indent=2)[:800])
