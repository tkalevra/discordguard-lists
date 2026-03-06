#!/usr/bin/env python3
"""
compile-lists.py — Merge community.txt and scraped-raw.txt into a JSON filter list.

Reads AdGuard plaintext format from both source files, deduplicates all entries,
and writes the merged result to lists/<target>.json.

Usage:
    python scripts/compile-lists.py --target child-safe
    python scripts/compile-lists.py --target family-safe
    python scripts/compile-lists.py --target teen
"""

import json
import argparse
import logging
import re
from datetime import date
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent.parent
SOURCES_DIR = REPO_ROOT / "sources"
LISTS_DIR = REPO_ROOT / "lists"

SOURCE_FILES = [
    SOURCES_DIR / "community.txt",
    SOURCES_DIR / "scraped-raw.txt",
]

TARGET_DESCRIPTIONS = {
    "child-safe": (
        "Strict child-safe filter list. Blocks all NSFW, adult, and age-inappropriate "
        "Discord servers, channels, and keywords."
    ),
    "family-safe": (
        "Family-safe filter list. Blocks explicit adult content and overtly harmful servers "
        "while permitting general teen/young adult communities."
    ),
    "teen": (
        "Teen filter list (13-17). Blocks explicitly pornographic, illegal, and harmful content "
        "while permitting general mature discussion, gaming communities, and age-appropriate social spaces."
    ),
}

# Patterns for each target that restrict which entries are included.
# teen profile drops some of the softer blocked_channel_patterns present in child-safe.
TEEN_EXCLUDED_CATEGORIES = {"mature", "suggestive", "horny", "feet", "fetish", "kink", "thirst"}
TEEN_EXCLUDED_KEYWORDS = {
    "sex", "cock", "dick", "pussy", "boobs", "tits", "ass", "cum",
    "masturbat", "orgasm", "handjob", "dildo", "vibrator",
}

ENTRY_RE = re.compile(r"^\|\|(?P<type>server|category|keyword):(?P<value>.+)$")


def parse_plaintext(path: Path) -> dict[str, set[str]]:
    """
    Parse an AdGuard-style plaintext filter file.

    Returns a dict with keys 'servers', 'categories', 'keywords',
    each mapping to a set of string values.
    """
    entries: dict[str, set[str]] = {
        "servers": set(),
        "categories": set(),
        "keywords": set(),
    }

    if not path.exists():
        log.warning("Source file not found, skipping: %s", path)
        return entries

    for lineno, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()

        # Skip blank lines and comment lines
        if not line or line.startswith("#") or line.startswith("!"):
            continue

        m = ENTRY_RE.match(line)
        if not m:
            log.debug("Unrecognised line %d in %s: %r", lineno, path.name, line)
            continue

        entry_type = m.group("type")
        value = m.group("value").strip()

        if entry_type == "server":
            entries["servers"].add(value)
        elif entry_type == "category":
            entries["categories"].add(value)
        elif entry_type == "keyword":
            entries["keywords"].add(value)

    log.info(
        "Parsed %s: %d servers, %d categories, %d keywords",
        path.name,
        len(entries["servers"]),
        len(entries["categories"]),
        len(entries["keywords"]),
    )
    return entries


def merge_entries(*parsed: dict[str, set[str]]) -> dict[str, set[str]]:
    """Merge multiple parsed entry dicts, deduplicating automatically via sets."""
    merged: dict[str, set[str]] = {"servers": set(), "categories": set(), "keywords": set()}
    for p in parsed:
        for key in merged:
            merged[key].update(p[key])
    return merged


def apply_target_filter(entries: dict[str, set[str]], target: str) -> dict[str, set[str]]:
    """Remove entries that don't apply to the given target profile."""
    if target == "teen":
        entries["categories"] = entries["categories"] - TEEN_EXCLUDED_CATEGORIES
        entries["keywords"] = entries["keywords"] - TEEN_EXCLUDED_KEYWORDS
    # family-safe keeps all entries from the merged set (same as child-safe for now;
    # could be refined with its own exclusion set in the future)
    return entries


def build_json(entries: dict[str, set[str]], target: str, version: str = "1.0.0") -> dict:
    return {
        "version": version,
        "updated": date.today().isoformat(),
        "description": TARGET_DESCRIPTIONS.get(target, f"{target} filter list."),
        "blocked_servers": sorted(entries["servers"]),
        "blocked_channel_patterns": sorted(entries["categories"]),
        "blocked_keywords": sorted(entries["keywords"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compile plaintext filter sources into a JSON filter list."
    )
    parser.add_argument(
        "--target",
        required=True,
        choices=list(TARGET_DESCRIPTIONS.keys()),
        help="Which filter list to generate.",
    )
    parser.add_argument(
        "--version",
        default="1.0.0",
        help="Version string to embed in the output JSON (default: %(default)s).",
    )
    args = parser.parse_args()

    # Parse all source files
    parsed_sources = [parse_plaintext(src) for src in SOURCE_FILES]

    # Merge and deduplicate
    merged = merge_entries(*parsed_sources)
    log.info(
        "Merged totals before filtering: %d servers, %d categories, %d keywords",
        len(merged["servers"]),
        len(merged["categories"]),
        len(merged["keywords"]),
    )

    # Apply target-specific exclusions
    filtered = apply_target_filter(merged, args.target)
    log.info(
        "After %r filtering: %d servers, %d categories, %d keywords",
        args.target,
        len(filtered["servers"]),
        len(filtered["categories"]),
        len(filtered["keywords"]),
    )

    # Build and write output JSON
    output = build_json(filtered, args.target, args.version)
    output_path = LISTS_DIR / f"{args.target}.json"
    LISTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    log.info("Wrote filter list to %s", output_path)


if __name__ == "__main__":
    main()
