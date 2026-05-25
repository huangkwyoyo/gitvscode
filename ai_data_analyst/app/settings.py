from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "outputs"
STATIC_DIR = BASE_DIR / "frontend"
TEMPLATE_DIR = BASE_DIR / "templates"

for path in [UPLOAD_DIR, OUTPUT_DIR, STATIC_DIR, TEMPLATE_DIR]:
    path.mkdir(parents=True, exist_ok=True)

