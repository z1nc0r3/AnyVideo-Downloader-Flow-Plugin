import sys
import os

# Add plugin/ and lib/ to sys.path so test modules can import from them
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PLUGIN_DIR = os.path.join(PROJECT_ROOT, "plugin")
LIB_DIR = os.path.join(PROJECT_ROOT, "lib")

for path in (PLUGIN_DIR, LIB_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)
