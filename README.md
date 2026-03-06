# Why?
Because discord owners are idiots that are lazy and lack imagination, as do governments. Before you go full tilt, it's vibe coded... I know, shocked pikkachu, but I had the idea, alongside others. So those options were:
* Get the gov't to force ISP's to utilize govt controlled DNS, in Canada that would be CIRA safe search, allowing individuals with the skills to change the dns at their whim, but overall removing ISP's from oversight and privitized snooping, alongside providing guardrails for individuals... this would have been much better and broader, but meh.
* or this.... which is where discord themselves should have gone, if only CEO's weren't egotistical clowns. So here I am 

# discordguard-lists

Community-maintained filter lists for [DiscordGuard](https://github.com/tkalevra/discordguard-lists), a browser extension providing parental controls for Discord. Like AdGuard or uBlock Origin filter lists, these lists are decoupled from the extension itself so they can be updated independently by the community — blocking servers by ID, channel name patterns, and keywords across three strictness tiers: `child-safe`, `family-safe`, and `teen`.

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

---

## Local Nightly Runner

The scraper and compiler run locally via a systemd user timer rather than CI.

```bash
# Install systemd user units
cp scripts/discordguard-lists.service ~/.config/systemd/user/
cp scripts/discordguard-lists.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now discordguard-lists.timer

# Verify
systemctl --user status discordguard-lists.timer

# Manual trigger
systemctl --user start discordguard-lists.service

# Check logs
journalctl --user -u discordguard-lists.service -f
```
