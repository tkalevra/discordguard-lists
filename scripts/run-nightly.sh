#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

cd "$REPO_DIR"

echo "[discordguard] $(date -u +%Y-%m-%dT%H:%M:%SZ) -- starting nightly update"

python3 scripts/scraper.py

python3 scripts/compile-lists.py --target child-safe
python3 scripts/compile-lists.py --target family-safe
python3 scripts/compile-lists.py --target teen

git add lists/ sources/scraped-raw.txt
git diff --staged --quiet && echo "[discordguard] no changes, skipping commit" && exit 0

git commit -m "chore: nightly list update $(date -u +%Y-%m-%d)"
git push origin main

echo "[discordguard] done"
