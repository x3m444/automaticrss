#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "→ git pull"
git pull

echo "→ pip install -r requirements.txt"
venv/bin/pip install -r requirements.txt -q

echo "→ playwright install chromium"
venv/bin/playwright install chromium --with-deps -q

echo "→ restart automaticrss"
sudo systemctl restart automaticrss

echo "✓ Update complet"
