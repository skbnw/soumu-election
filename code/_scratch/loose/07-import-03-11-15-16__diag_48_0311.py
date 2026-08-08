import json
from collections import Counter
from pathlib import Path

facts = json.loads(Path(r"C:\Users\SKBNW\Documents\Github\soumu-election\data\shugiin48\normalized\facts.json").read_text(encoding="utf-8"))
rows = [f for f in facts if f.get("source_code") == "03-11"]
print("n", len(rows))
print("metrics", Counter(f["metric"] for f in rows))
print("blocks", len({f.get("pr_block") for f in rows}))
# duplicate list positions?
keys = Counter((f.get("pr_block"), f.get("party"), f.get("candidate"), f.get("value")) for f in rows if f["metric"]=="pr_list_position")
print("dup list keys", sum(1 for k,v in keys.items() if v>1), "max", max(keys.values()))
print("sample dups", [ (k,v) for k,v in keys.most_common(5)])
# party votes count
pv = [f for f in rows if f["metric"]=="party_votes"]
print("party_votes", len(pv), "unique", len({(f.get("pr_block"), f.get("party")) for f in pv}))
