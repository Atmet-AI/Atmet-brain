#!/bin/sh
# Install a versioned GitHub wheel into an isolated, per-user uv tool environment.
set -eu

version="${1:-0.6.1}"
case "$version" in
  --help|-h)
    printf '%s\n' 'Usage: sh install.sh [VERSION]' 'Requires uv and curl. Installs for the current user; never uses sudo.'
    exit 0 ;;
esac
if ! printf '%s\n' "$version" | LC_ALL=C grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$'; then
  printf '%s\n' 'Choose a release version such as 0.6.1.' >&2
  exit 1
fi
if ! command -v uv >/dev/null 2>&1; then
  printf '%s\n' 'Install uv first: https://docs.astral.sh/uv/getting-started/installation/' >&2
  exit 1
fi
command -v curl >/dev/null 2>&1 || { printf '%s\n' 'curl is required.' >&2; exit 1; }
temporary=$(mktemp -d)
trap 'rm -rf "$temporary"' EXIT HUP INT TERM
wheel="atmet_brain-${version}-py3-none-any.whl"
base="https://github.com/anashamad9/Atmet-brain/releases/download/v${version}"
printf '%s\n' "Installing Atmet Brain ${version} for this user..."
curl --proto '=https' --tlsv1.2 -fsSL "$base/$wheel" -o "$temporary/$wheel"
curl --proto '=https' --tlsv1.2 -fsSL "$base/SHA256SUMS.txt" -o "$temporary/SHA256SUMS.txt"
expected=$(awk -v name="$wheel" '$2 == name {print $1}' "$temporary/SHA256SUMS.txt")
if command -v sha256sum >/dev/null 2>&1; then
  actual=$(sha256sum "$temporary/$wheel" | awk '{print $1}')
else
  actual=$(shasum -a 256 "$temporary/$wheel" | awk '{print $1}')
fi
if [ -z "$expected" ] || [ "$expected" != "$actual" ]; then
  printf '%s\n' 'Release checksum verification failed. Nothing installed.' >&2
  exit 1
fi
uv tool install --python 3.12 --force "$temporary/$wheel"
printf '\n%s\n' 'Atmet Brain installed.' 'Next: atmet-brain setup' 'If the command is missing, run uv tool update-shell and open a new terminal.'
