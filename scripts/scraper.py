#!/usr/bin/env python3
"""
scraper.py — Scrape Disboard.org for adult/NSFW-tagged Discord servers.

Writes results to sources/scraped-raw.txt in AdGuard plaintext filter format.
Run from the repo root:
    python scripts/scraper.py
"""

import re
import time
import random
import logging
import argparse
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

OUTPUT_FILE = Path(__file__).parent.parent / "sources" / "scraped-raw.txt"

BASE_URL = "https://disboard.org"
SEARCH_TAGS = ["nsfw", "adult", "18+", "hentai", "explicit"]
MAX_PAGES_PER_TAG = 5

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 "
        "DiscordGuardBot/1.0 (+https://github.com/YOUR_ORG/discordguard-lists)"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Disboard server invite URLs contain the server ID in the path after /server/join/
SERVER_ID_RE = re.compile(r"/server/join/(\d{17,19})")
# Also try direct server page links
SERVER_PAGE_RE = re.compile(r"/servers?/(\d{17,19})")


def fetch_page(session: requests.Session, url: str) -> BeautifulSoup | None:
    """Fetch a URL and return a BeautifulSoup object, or None on error."""
    try:
        resp = session.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except requests.HTTPError as exc:
        log.warning("HTTP error fetching %s: %s", url, exc)
    except requests.RequestException as exc:
        log.warning("Request failed for %s: %s", url, exc)
    return None


def extract_server_ids(soup: BeautifulSoup) -> set[str]:
    """Extract Discord server IDs from a Disboard listing page."""
    ids: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        m = SERVER_ID_RE.search(href) or SERVER_PAGE_RE.search(href)
        if m:
            ids.add(m.group(1))

    return ids


def extract_tags(soup: BeautifulSoup) -> list[str]:
    """Extract category/tag names visible on the listing page."""
    tags: list[str] = []
    for tag_el in soup.select(".server-tag, .tag, [class*='tag']"):
        text = tag_el.get_text(strip=True).lower()
        if text:
            tags.append(text)
    return tags


def scrape_tag(session: requests.Session, tag: str, max_pages: int) -> dict[str, set[str]]:
    """Scrape Disboard for servers with the given tag. Returns {server_id: {tags}}."""
    results: dict[str, set[str]] = {}

    for page in range(1, max_pages + 1):
        url = f"{BASE_URL}/servers/tag/{tag}/{page}"
        log.info("Fetching tag=%r page=%d — %s", tag, page, url)

        soup = fetch_page(session, url)
        if soup is None:
            break

        # Stop if Disboard returns an empty/no-results page
        server_cards = soup.select(".server-listing, .server-card, [class*='server']")
        if not server_cards:
            log.info("No server cards found on page %d for tag %r, stopping.", page, tag)
            break

        ids = extract_server_ids(soup)
        page_tags = extract_tags(soup)

        for sid in ids:
            results.setdefault(sid, set()).update(page_tags)
            results[sid].add(tag)

        log.info("  → Found %d server IDs on this page.", len(ids))

        # Rate limiting: 1–2 second random delay between requests
        delay = random.uniform(1.0, 2.0)
        log.debug("Sleeping %.2fs", delay)
        time.sleep(delay)

    return results


def write_output(results: dict[str, set[str]]) -> None:
    """Write scraped results to sources/scraped-raw.txt in AdGuard plaintext format."""
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# DiscordGuard Scraped Raw Data",
        "# ============================================================",
        "# THIS FILE IS AUTO-GENERATED. DO NOT EDIT MANUALLY.",
        "#",
        f"# Generated: {datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "# Source:    https://disboard.org (public server listings)",
        "# Script:    scripts/scraper.py",
        "# ============================================================",
        "",
        "! === SCRAPED BLOCKED SERVERS ===",
    ]

    for server_id, tags in sorted(results.items()):
        tag_str = ", ".join(sorted(tags))
        lines.append(f"! tags: {tag_str}")
        lines.append(f"||server:{server_id}")

    OUTPUT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log.info("Wrote %d server entries to %s", len(results), OUTPUT_FILE)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape Disboard for NSFW/adult servers.")
    parser.add_argument(
        "--tags",
        nargs="+",
        default=SEARCH_TAGS,
        help="Disboard tags to search (default: %(default)s)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=MAX_PAGES_PER_TAG,
        help="Max listing pages to fetch per tag (default: %(default)s)",
    )
    args = parser.parse_args()

    session = requests.Session()
    all_results: dict[str, set[str]] = {}

    for tag in args.tags:
        tag_results = scrape_tag(session, tag, args.max_pages)
        for sid, tags in tag_results.items():
            all_results.setdefault(sid, set()).update(tags)

    log.info("Total unique servers scraped: %d", len(all_results))
    write_output(all_results)


if __name__ == "__main__":
    main()
