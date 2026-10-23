"""Explicit operator compatibility mode for pre-classification regression fixtures.

New security tests use the default restricted intake. Old feature fixtures keep their
previous trusted-import setup so those tests continue isolating their original behavior.
"""

from pathlib import Path


def legacy_imports(home):
    home = Path(home);home.mkdir(parents=True, exist_ok=True)
    (home / "config.toml").write_text("[brain]\nrequire_document_classification = false\n")
    return home
