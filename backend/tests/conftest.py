"""
conftest.py — puts backend/ on sys.path so `import main` resolves when
pytest runs from either the repo root or backend/.
"""
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
