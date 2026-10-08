from pathlib import Path
import json
import sys
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "backend"))
from app.schemas import LabelBundle
(root / "docs" / "label-bundle.schema.json").write_text(json.dumps(LabelBundle.model_json_schema(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
