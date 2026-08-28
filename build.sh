#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

rm -rf build dist

docker run --rm --name uc-appletv-keyboard-builder \
  --user="$(id -u):$(id -g)" \
  -v "$ROOT:/workspace" \
  docker.io/unfoldedcircle/r2-pyinstaller:3.11.13 \
  bash -lc 'cd /workspace && \
    python -m pip install -r requirements.txt && \
    pyinstaller --clean --onedir --name intg-appletv-keyboard \
      intg-appletv-keyboard/driver.py'

echo "Built: dist/intg-appletv-keyboard/"
