import sys
from pathlib import Path

# The app modules live in src/ and import each other by bare name.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
