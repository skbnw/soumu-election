from pathlib import Path
DATA = Path(r"C:\Users\SKBNW\Documents\Github\soumu-election\data")
for kaiji in (45, 46, 47, 48):
    raw = DATA / f"shugiin{kaiji}/raw"
    print(f"\n## {kaiji}")
    for p in sorted(raw.glob("03-16*")):
        print(" ", p.name, "dir" if p.is_dir() else p.stat().st_size)
        if p.is_dir():
            for c in sorted(p.rglob("*")):
                if c.is_file():
                    print("   ", c.name, c.stat().st_size)
