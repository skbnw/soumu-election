import pdfplumber
from pathlib import Path
from pypdf import PdfReader

DATA = Path(r"C:\Users\SKBNW\Documents\Github\soumu-election\data")
for kaiji in (46, 47):
    path = next((DATA / f"shugiin{kaiji}/raw").glob("03-16*.pdf"))
    print(f"\n## {kaiji} {path.name}")
    reader = PdfReader(path)
    print("pages", len(reader.pages), "attachments", list(reader.attachments.keys()) if reader.attachments else None)
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages[:2], 1):
            text = page.extract_text() or ""
            print(f"page{i} len={len(text)} head={text[:400]!r}")
            print("tables", len(page.extract_tables() or []))
