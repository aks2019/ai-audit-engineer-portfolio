#!/usr/bin/env python3
import glob, py_compile, os

HERE = os.path.dirname(__file__)
PAGES_DIR = os.path.join(HERE, "..", "pages")

for p in sorted(glob.glob(os.path.join(PAGES_DIR, "*.py"))):
    with open(p, "r", encoding="utf-8") as f:
        content = f.read()
    has_rag = "render_rag_report_section" in content
    has_draft = "render_draft_review_section" in content
    has_stage = "stage_findings" in content
    if has_rag or has_draft or has_stage:
        name = os.path.basename(p)
        try:
            py_compile.compile(p, doraise=True)
            status = "OK"
        except Exception as e:
            status = f"ERR: {e}"
        print(f"{name:25s} RAG={has_rag} Draft={has_draft} Stage={has_stage} [{status}]")
