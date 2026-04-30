"""
pytest configuration: add src/ to sys.path so test modules can import
the application source without installation.
"""
import sys
import os

# Ensure src/ is on the path so 'from logger import log' etc. work in tests
_SRC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src')
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)
