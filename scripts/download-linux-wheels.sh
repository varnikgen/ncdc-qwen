#!/bin/sh
# Скачать manylinux-колёса для python:3.11-slim (на машине С интернетом).
set -e
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
DEST="$ROOT/vendor/py311-linux"
mkdir -p "$DEST"
python3 -m pip download \
  -r "$ROOT/requirements.txt" \
  -d "$DEST" \
  --python-version 311 \
  --platform manylinux_2_17_x86_64 \
  --implementation cp \
  --abi cp311 \
  --only-binary=:all: \
  --trusted-host pypi.org \
  --trusted-host files.pythonhosted.org
echo "Wheels saved to $DEST"
ls -lh "$DEST"
