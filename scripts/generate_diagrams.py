"""Keep standalone diagram sources synchronized with documentation blocks."""

import argparse
from pathlib import Path
import re


def diagram_sources(root):
    """Map generated names to their authoritative Markdown block contents."""
    result = {}
    sources = [root / "README.md", *sorted((root / "docs").glob("*.md"))]
    for source in sources:
        for index, block in enumerate(re.findall(r"```mermaid\n(.*?)```", source.read_text(encoding="utf-8"), re.S), 1):
            stem = "overview" if source == root / "README.md" else source.stem
            result[f"{stem}-{index}.mmd"] = block.strip() + "\n"
    return result


def diagram_errors(root):
    expected = diagram_sources(root)
    directory = root / "docs/diagrams"
    actual = {p.name: p for p in directory.glob("*.mmd")}
    errors = []
    for name, body in expected.items():
        if name not in actual or actual[name].read_text(encoding="utf-8") != body:
            errors.append("docs/diagrams/" + name + ": missing or stale; run scripts/generate_diagrams.py")
    errors.extend("docs/diagrams/" + name + ": obsolete generated diagram" for name in sorted(actual.keys() - expected.keys()))
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check synchronization without changing files")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.check:
        errors = diagram_errors(root)
        if errors:
            parser.exit(1, "\n".join(errors) + "\n")
        print(f"PASS: {len(diagram_sources(root))} generated diagrams match their Markdown sources")
        return
    directory = root / "docs/diagrams"
    directory.mkdir(exist_ok=True)
    expected = diagram_sources(root)
    for path in directory.glob("*.mmd"):
        if path.name not in expected:
            path.unlink()
    for name, body in expected.items():
        (directory / name).write_text(body, encoding="utf-8")
    print(f"Generated {len(expected)} standalone Mermaid diagram sources")


if __name__ == "__main__":
    main()
