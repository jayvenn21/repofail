#!/usr/bin/env bash
# Install repofail — deterministic runtime compatibility analyzer
# Usage: curl -sSL https://raw.githubusercontent.com/jayvenn21/repofail/main/install.sh | bash

set -e

if command -v pipx &>/dev/null; then
  echo "Installing repofail via pipx (isolated)..."
  pipx install repofail
elif command -v pip3 &>/dev/null; then
  echo "Installing repofail via pip..."
  pip3 install repofail
elif command -v pip &>/dev/null; then
  echo "Installing repofail via pip..."
  pip install repofail
else
  echo "Error: need pip or pipx. Install Python 3.10+ and run: pip install repofail"
  exit 1
fi

echo "Done. Run: repofail --help"
