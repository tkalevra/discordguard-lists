# discordguard-lists

Community-maintained filter lists for [DiscordGuard](https://github.com/YOUR_ORG/discordguard), a browser extension providing parental controls for Discord. Like AdGuard or uBlock Origin filter lists, these lists are decoupled from the extension itself so they can be updated independently by the community — blocking servers by ID, channel name patterns, and keywords across three strictness tiers: `child-safe`, `family-safe`, and `teen`.

---

## JSON Format (`lists/*.json`)

```json
{
  "version": "1.0.0",
  "updated": "2026-03-06",
  "description": "Human-readable description of this list.",
  "blocked_servers": [
    "1094827361052840007"
  ],
  "blocked_channel_patterns": [
    "nsfw",
    "18+"
  ],
  "blocked_keywords": [
    "pornhub",
    "onlyfans"
  ]
}
```

| Field | Type | Description |
|---|---|---|
| `version` | string | Semver list version |
| `updated` | string | ISO 8601 date of last update |
| `blocked_servers` | string[] | Discord server snowflake IDs (18-digit) |
| `blocked_channel_patterns` | string[] | Channel name substrings to block |
| `blocked_keywords` | string[] | Keywords triggering a block in messages/descriptions |

---

## Plaintext Community Format (`sources/community.txt`)

Sources use AdGuard-style plaintext filter syntax:

```
! comment line (displayed in diff, ignored by compiler)
# also a comment (ignored entirely)

||server:1094827361052840007       — block a specific server by snowflake ID
||category:nsfw                   — block channels whose name contains this string
||keyword:onlyfans                — block messages/descriptions containing this term
```

---

## Contributing

1. Add your entries to `sources/community.txt` using the plaintext format above.
2. Open a pull request — include a brief comment (`! reason: ...`) above new server blocks.
3. After merge, a maintainer runs the compile script to regenerate the JSON lists:

```bash
python scripts/compile-lists.py --target child-safe
python scripts/compile-lists.py --target family-safe
python scripts/compile-lists.py --target teen
```

To scrape fresh data from Disboard and regenerate from scratch:

```bash
python scripts/scraper.py
python scripts/compile-lists.py --target child-safe
```

**Do not edit `lists/*.json` or `sources/scraped-raw.txt` directly** — both are generated files.
