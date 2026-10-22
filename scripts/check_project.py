"""Check public repository hygiene, local documentation links and generated schemas."""

import ast
import json
from pathlib import Path
import re
import sys
import tempfile
import tomllib
from urllib.parse import unquote

from atmet_brain import Brain, __version__
from atmet_brain.rpc import openapi
from generate_diagrams import diagram_errors

ROOT = Path(__file__).resolve().parents[1]
IGNORE = {".git", ".venv", "__pycache__", "build", "dist"}
errors, count = [], 0
package = tomllib.loads((ROOT / "pyproject.toml").read_text())
if package["project"]["version"] != __version__:
    errors.append("Package and runtime versions differ")
if not re.search(r"^## " + re.escape(__version__) + r"(?:\s|$)", (ROOT / "CHANGELOG.md").read_text(), re.M):
    errors.append("Current version is missing from CHANGELOG.md")
for path in ROOT.rglob("*"):
    if not path.is_file() or any(part in IGNORE or part.endswith(".egg-info") for part in path.relative_to(ROOT).parts):
        continue
    if path.suffix in {".pyc", ".pyo"}:
        continue
    try:
        body = path.read_text(encoding="utf-8")
    except UnicodeError:
        errors.append(str(path.relative_to(ROOT)) + ": unexpected binary public file")
        continue
    count += 1
    if "\u2014" in body:
        errors.append(str(path.relative_to(ROOT)) + ": forbidden punctuation")
    if re.search(r"atmet_[A-Za-z0-9_-]{40,}", body):
        errors.append(str(path.relative_to(ROOT)) + ": possible bearer credential")
    if (str(Path.home()) + "/") in body:
        errors.append(str(path.relative_to(ROOT)) + ": private workspace path")
    if path.suffix == ".py":
        try:
            ast.parse(body, filename=str(path))
        except SyntaxError as error:
            errors.append(str(error))
    if path.suffix == ".json":
        try:
            json.loads(body)
        except ValueError:
            errors.append(str(path.relative_to(ROOT)) + ": invalid JSON")
    if path.suffix == ".md":
        if body.count("```") % 2:
            errors.append(str(path.relative_to(ROOT)) + ": unclosed code fence")
        for value in re.findall(r"\[[^\]]*\]\(([^)]+)\)", body):
            target = value.split("#", 1)[0]
            if not target or "://" in target or target.startswith("mailto:"):
                continue
            candidate = (path.parent / unquote(target)).resolve()
            if not candidate.is_relative_to(ROOT) or not candidate.exists():
                errors.append(str(path.relative_to(ROOT)) + ": broken or nonportable link " + target)
with tempfile.TemporaryDirectory(prefix="atmet-check-") as home:
    expected = openapi(Brain(home))
schema = ROOT / "docs/openapi.json"
if not schema.exists() or json.loads(schema.read_text()) != expected:
    errors.append("OpenAPI schema is missing or stale; run scripts/generate_openapi.py")
errors.extend(diagram_errors(ROOT))
if errors:
    print("\n".join(errors), file=sys.stderr)
    raise SystemExit(1)
print(f"PASS: {count} public text files, Python syntax, JSON, local links, punctuation, credential scan, OpenAPI and diagram synchronization")
