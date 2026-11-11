"""Export the API contract without connecting to external services."""
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "services/backend"))
from app.main import app

target = root / "contracts/openapi.json"
target.parent.mkdir(exist_ok=True)
target.write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
print(f"Exported {len(app.openapi()['paths'])} API paths")
