#!/usr/bin/env python3
"""Copy the dashboard HTML into the docs directory for GitHub Pages."""
from __future__ import annotations

import pathlib
import shutil

ROOT = pathlib.Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "index.html"
DOCS = ROOT / "docs" / "index.html"

if not FRONTEND.exists():
    raise SystemExit(f"Frontend file not found: {FRONTEND}")

DOCS.parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile(FRONTEND, DOCS)
print(f"Copied {FRONTEND} -> {DOCS}")
