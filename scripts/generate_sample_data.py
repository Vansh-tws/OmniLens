from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.sample_data import write_sample_files

written = write_sample_files(ROOT / "samples")
for name, path in written.items():
    print(f"Created {name}: {path.relative_to(ROOT)}")
