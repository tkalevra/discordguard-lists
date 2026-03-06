#!/usr/bin/env python3
"""
scraper.py — Scrape Disboard.org for adult/NSFW-tagged Discord servers.

Writes results to sources/scraped-raw.txt in AdGuard plaintext filter format,
wrapped in ! BEGIN SCRAPED / ! END SCRAPED markers so compile-lists.py can
replace only the scraped section without touching manually maintained entries.

Run from the repo root:
    python scripts/scraper.py
"""

import re
import sys
import time
import random
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

OUTPUT_FILE = Path(__file__).parent.parent / "sources" / "scraped-raw.txt"

BASE_URL = "https://disboard.org"
MAX_PAGES_PER_TAG = 10  # 24 servers/page → ~240 servers/tag max

# Pass 1: feed child-safe and family-safe lists
HARD_BLOCKED_TAGS = [
    "nsfw", "adult", "18+", "hentai", "gore",
    "explicit", "porn", "lewd", "erotic", "xxx",
]

# Pass 2: feed teen list (flagged, not hard-blocked)
TEEN_FLAGGED_TAGS = ["mature", "suggestive", "dating", "relationship"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "DNT": "1",
}

# Matches /server/<snowflake> — Disboard server page links
SERVER_HREF_RE = re.compile(r"^/server/(\d{17,19})(?:/|$)")


class ScrapedServer:
    __slots__ = ("server_id", "name", "tags")

    def __init__(self, server_id: str, name: str, tags: set[str]):
        self.server_id = server_id
        self.name = name
        self.tags = tags


def fetch_page(session: requests.Session, url: str) -> BeautifulSoup | None:
    """Fetch a URL and return a BeautifulSoup object, or None on any error."""
    try:
        resp = session.get(url, headers=HEADERS, timeout=20)
        if resp.status_code == 403:
            print(f"[scraper] 403 Cloudflare block on {url} — skipping tag", file=sys.stderr)
            return None
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except requests.HTTPError as exc:
        print(f"[scraper] HTTP {exc.response.status_code} on {url}", file=sys.stderr)
    except requests.RequestException as exc:
        print(f"[scraper] Request failed for {url}: {exc}", file=sys.stderr)
    return None


def parse_server_cards(soup: BeautifulSoup, scraped_tag: str) -> list[ScrapedServer]:
    """Extract server info from all cards on a Disboard listing page."""
    results: dict[str, ScrapedServer] = {}

    for a in soup.find_all("a", href=True):
        m = SERVER_HREF_RE.match(a["href"])
        if not m:
            continue

        server_id = m.group(1)
        if server_id in results:
            continue

        # Walk up to the server card container to grab name + tags
        card = a.find_parent(class_=lambda c: c and "server" in " ".join(c).lower()) if a else None

        name = "unknown"
        if card:
            name_el = card.find(class_=lambda c: c and "name" in " ".join(c).lower())
            if name_el:
                name = name_el.get_text(strip=True)[:80]
        if name == "unknown":
            text = a.get_text(separator=" ", strip=True)
            if text:
                name = text[:80]

        card_tags: set[str] = {scraped_tag}
        if card:
            for tag_el in card.find_all(class_=lambda c: c and "tag" in " ".join(c).lower()):
                t = tag_el.get_text(strip=True).lower()
                if t and len(t) < 40:
                    card_tags.add(t)

        results[server_id] = ScrapedServer(server_id=server_id, name=name, tags=card_tags)

    return list(results.values())


def scrape_tag(session: requests.Session, tag: str, max_pages: int) -> list[ScrapedServer]:
    """
    Scrape Disboard for servers listed under `tag`.
    URL pattern: https://disboard.org/servers/tag/<tag>?page=<n>
    Returns up to max_pages * ~24 servers.
    """
    accumulated: dict[str, ScrapedServer] = {}

    for page in range(1, max_pages + 1):
        url = f"{BASE_URL}/servers/tag/{tag}?page={page}"
        print(f"[scraper] tag={tag!r:<14}  page={page:2d}  {url}")

        for attempt in range(2):
            response = requests.get(url, headers=HEADERS, timeout=15)
            if response.status_code == 429:
                wait = 60 + random.uniform(10, 20)
                print(f'[scraper] HTTP 429 on {url} — waiting {wait:.0f}s before retry')
                time.sleep(wait)
                continue
            break
        else:
            print(f'[scraper] HTTP 429 persists on {url} — skipping')
            continue

        if response.status_code == 403:
            print(f'[scraper] 403 on {url} — skipping tag')
            break

        soup = BeautifulSoup(response.text, "html.parser")

        cards = parse_server_cards(soup, tag)

        if not cards:
            print(f"[scraper]   → no server cards found — end of results for tag={tag!r}")
            break

        for srv in cards:
            if srv.server_id in accumulated:
                accumulated[srv.server_id].tags.update(srv.tags)
            else:
                accumulated[srv.server_id] = srv

        print(f"[scraper]   → {len(cards)} servers this page  ({len(accumulated)} total for tag={tag!r})")

        # Rate limiting: 8–15 second random sleep between page requests
        delay = random.uniform(8, 15)
        time.sleep(delay)

    return list(accumulated.values())


def build_scraped_block(
    hard_servers: list[ScrapedServer],
    teen_servers: list[ScrapedServer],
    timestamp: str,
) -> str:
    """Return the full ! BEGIN SCRAPED ... ! END SCRAPED block as a string."""
    total = len(hard_servers) + len(teen_servers)
    lines = [
        "! BEGIN SCRAPED",
        f"! Scraped: {timestamp}",
        "! Source: disboard.org",
        f"! Tags scraped (hard-blocked): {', '.join(HARD_BLOCKED_TAGS)}",
        f"! Tags scraped (teen-flagged): {', '.join(TEEN_FLAGGED_TAGS)}",
        f"! Total servers: {total}",
        "!",
        "! SECTION hard-blocked",
        "! Servers from hard-blocked tags — included in child-safe and family-safe lists",
    ]

    for srv in sorted(hard_servers, key=lambda s: s.server_id):
        tag_str = ", ".join(sorted(srv.tags))
        clean_name = srv.name.replace("\n", " ").strip() or "unknown"
        lines.append(f"||server:{srv.server_id}  ! name: {clean_name} | tags: {tag_str}")

    lines += [
        "!",
        "! SECTION teen-flagged",
        "! Servers from teen-flagged tags — included in teen list only",
    ]

    for srv in sorted(teen_servers, key=lambda s: s.server_id):
        tag_str = ", ".join(sorted(srv.tags))
        clean_name = srv.name.replace("\n", " ").strip() or "unknown"
        lines.append(f"||server:{srv.server_id}  ! name: {clean_name} | tags: {tag_str}")

    lines.append("! END SCRAPED")
    return "\n".join(lines)


def write_output(hard_servers: list[ScrapedServer], teen_servers: list[ScrapedServer]) -> None:
    """
    Write scraped results to sources/scraped-raw.txt.
    Replaces the existing BEGIN/END block in-place if one exists,
    otherwise writes a fresh file with the standard header.
    """
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    scraped_block = build_scraped_block(hard_servers, teen_servers, timestamp)

    existing = OUTPUT_FILE.read_text(encoding="utf-8") if OUTPUT_FILE.exists() else ""
    begin_marker = "! BEGIN SCRAPED"
    end_marker = "! END SCRAPED"

    if begin_marker in existing and end_marker in existing:
        # Replace just the scraped block, preserving anything before/after
        before = existing[: existing.index(begin_marker)].rstrip("\n")
        after_end_pos = existing.index(end_marker) + len(end_marker)
        after = existing[after_end_pos:].lstrip("\n")
        new_content = before + ("\n" if before else "") + scraped_block + ("\n" + after if after else "\n")
    else:
        header = (
            "# DiscordGuard Scraped Raw Data\n"
            "# ============================================================\n"
            "# THIS FILE IS AUTO-GENERATED. DO NOT EDIT MANUALLY.\n"
            "#\n"
            "# Regenerate by running: python scripts/scraper.py\n"
            "# Compile into JSON:     python scripts/compile-lists.py --target <profile>\n"
            "# ============================================================\n\n"
        )
        new_content = header + scraped_block + "\n"

    OUTPUT_FILE.write_text(new_content, encoding="utf-8")
    total = len(hard_servers) + len(teen_servers)
    print(
        f"[scraper] wrote {len(hard_servers)} hard-blocked + {len(teen_servers)} teen-flagged"
        f" = {total} total servers to {OUTPUT_FILE}"
    )


def main() -> None:
    session = requests.Session()

    print(f'[scraper] estimated runtime: ~{(len(HARD_BLOCKED_TAGS) + len(TEEN_FLAGGED_TAGS)) * MAX_PAGES_PER_TAG * 12 // 60} minutes at current rate limits')

    # Pass 1: hard-blocked tags → child-safe / family-safe
    hard_accumulated: dict[str, ScrapedServer] = {}
    print("[scraper] === Pass 1: hard-blocked tags ===")
    for tag in HARD_BLOCKED_TAGS:
        for srv in scrape_tag(session, tag, MAX_PAGES_PER_TAG):
            if srv.server_id in hard_accumulated:
                hard_accumulated[srv.server_id].tags.update(srv.tags)
            else:
                hard_accumulated[srv.server_id] = srv
        time.sleep(random.uniform(20, 40))

    # Pass 2: teen-flagged tags → teen list only
    teen_accumulated: dict[str, ScrapedServer] = {}
    print("[scraper] === Pass 2: teen-flagged tags ===")
    for tag in TEEN_FLAGGED_TAGS:
        for srv in scrape_tag(session, tag, MAX_PAGES_PER_TAG):
            if srv.server_id in teen_accumulated:
                teen_accumulated[srv.server_id].tags.update(srv.tags)
            else:
                teen_accumulated[srv.server_id] = srv
        time.sleep(random.uniform(20, 40))

    # Servers already in the hard list should not appear separately in teen
    for sid in hard_accumulated:
        teen_accumulated.pop(sid, None)

    print(f"[scraper] hard-blocked unique servers: {len(hard_accumulated)}")
    print(f"[scraper] teen-flagged unique servers:  {len(teen_accumulated)}")

    write_output(list(hard_accumulated.values()), list(teen_accumulated.values()))


if __name__ == "__main__":
    main()
