#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "→ git pull"
git pull

echo "→ pip install -r requirements.txt"
venv/bin/pip install -r requirements.txt -q

echo "→ restart automaticrss"
sudo systemctl restart automaticrss

echo "✓ Update complet"
