"""
pytest configuration — add backend/ and the repo root to sys.path so
tests can import `main` and `ai_module` without installing packages.
"""

import os
import sys

_backend_dir = os.path.dirname(os.path.abspath(__file__))
_repo_root = os.path.normpath(os.path.join(_backend_dir, ".."))
for _path in (_backend_dir, _repo_root):
    if _path not in sys.path:
        sys.path.insert(0, _path)
