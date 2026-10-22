"""Keep standalone diagram sources synchronized with documentation blocks."""

from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
destination = root / "docs/diagrams"
destination.mkdir(exist_ok=True)
sources = [root / "README.md", *sorted((root / "docs").glob("*.md"))]
for source in sources:
    for index, block in enumerate(re.findall(r"```mermaid\n(.*?)```", source.read_text(), re.S), 1):
        stem = "overview" if source == root / "README.md" else source.stem
        (destination / f"{stem}-{index}.mmd").write_text(block.strip() + "\n")
print("Generated standalone Mermaid diagram sources")
