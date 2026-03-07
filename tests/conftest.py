import sys
import pathlib

# Ensure repo root is on sys.path so pytest can import local packages
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
