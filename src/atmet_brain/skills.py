"""Import explicitly listed portable skill resources without executing code."""

from pathlib import Path

from .connectors.files import read_contained
from .errors import require
from .util import loads, safe_resource_path, uid


def install_skill(brain, actor, space_id, package, artifact_id=None, expected_revision=0):
    root = Path(package).expanduser()
    require(root.is_dir() and not root.is_symlink(), "invalid_package", "Choose a non-symlink skill directory.")
    root = root.resolve()
    manifest = loads(read_contained(root, "manifest.json"))
    require(isinstance(manifest, dict) and set(manifest) <= {"name", "description", "inputs", "outputs", "resources", "required_tools", "checks", "dependencies"},
            "invalid_package", "Unknown skill manifest field.")
    resources = manifest.get("resources", [])
    require(isinstance(resources, list) and len(resources) <= 40, "invalid_package", "List up to 40 resource paths.")
    body = {"description": manifest["description"], "instructions": read_contained(root, "SKILL.md"),
            "inputs": manifest.get("inputs", []), "outputs": manifest.get("outputs", []),
            "required_tools": manifest.get("required_tools", []), "checks": manifest.get("checks", []),
            "resources": {safe_resource_path(path): read_contained(root, path) for path in resources}}
    return brain.propose_artifact(actor, space_id, "skill", manifest["name"], body, expected_revision,
                                  artifact_id=artifact_id, dependencies=manifest.get("dependencies", []),
                                  reason="Imported portable skill package", idempotency_key=uid("install"))
