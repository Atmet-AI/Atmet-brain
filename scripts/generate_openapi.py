"""Generate documentation from the actual public operation registry."""

import json
from pathlib import Path
import tempfile

from atmet_brain import Brain
from atmet_brain.rpc import openapi

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="atmet-schema-") as home:
    result = openapi(Brain(home))
(root / "docs/openapi.json").write_text(json.dumps(result, indent=2) + "\n")
print("Generated docs/openapi.json")
