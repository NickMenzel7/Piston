#!/usr/bin/env bash
set -euo pipefail

echo "Installing build deps..."
python -m pip install --upgrade pip
pip install pyinstaller

ONEFILE=${1:-}
if [[ "$ONEFILE" == "onefile" ]]; then
  echo "Building single-file executable..."
  pyinstaller --noconfirm --onefile --name piston Piston.py
else
  echo "Building directory-based bundle..."
  pyinstaller --noconfirm --name piston Piston.py
fi

echo "Build complete. Check 'dist' and 'build' directories."