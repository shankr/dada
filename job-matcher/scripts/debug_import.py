#!/usr/bin/env python3
import sys
from pathlib import Path

print("--- Python version ---")
print(sys.version)
print("--- Working directory ---")
print(Path.cwd())
print("--- Files in src/output/ ---")
for p in Path("src/output").iterdir():
    print(f"  {p.name} (size: {p.stat().st_size})")
print("--- __init__.py files ---")
for p in Path("src").rglob("__init__.py"):
    print(f"  {p} (size: {p.stat().st_size})")
print("--- sys.path ---")
for i, p in enumerate(sys.path):
    print(f"  [{i}] {p}")
print("--- Import test ---")
sys.path.insert(0, str(Path("src/main.py").parent.parent))
print(f"sys.path[0]: {sys.path[0]}")
print(f"resolved: {Path(sys.path[0]).resolve()}")
try:
    from src.output.report_generator import ReportGenerator
    print("IMPORT OK")
except Exception as e:
    print(f"IMPORT FAILED: {e}")
