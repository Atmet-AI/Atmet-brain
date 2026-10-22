"""Do not publish a launcher until its exact engine exists at the official PyPI project."""

import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

root = Path(__file__).resolve().parents[1]
version = json.loads((root / "npm/atmet-brain/package.json").read_text())["atmetBrain"]["engineVersion"]
try:
    with urlopen("https://pypi.org/pypi/atmet-brain/" + version + "/json", timeout=30) as response:
        release = json.load(response)
except (HTTPError, URLError, ValueError):
    raise SystemExit("The matching official PyPI engine is not available. Publish/verify it before npm.") from None
urls = release["info"].get("project_urls") or {}
expected = "https://github.com/anashamad9/Atmet-brain"
if release["info"]["version"] != version or urls.get("Repository", "").rstrip("/") != expected:
    raise SystemExit("PyPI release identity does not match the expected Atmet project.")
if not any(item["filename"].endswith(".whl") and not item.get("yanked") for item in release.get("urls", [])):
    raise SystemExit("The engine release has no available wheel.")
print("PASS: matching Atmet engine wheel exists on PyPI")
