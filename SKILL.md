---
name: bike-advisor
description: Use when Dave wants to find a used bike for sale in a specific city, with Reddit-informed brand/criteria research combined with Craigslist and Facebook Marketplace listing search
---

# Bike Finder

CLI tool that researches bike recommendations on Reddit, then searches Craigslist and Facebook Marketplace for listings, scoring and ranking results by brand relevance, price, and condition keywords.

## Script Location

```
~/.claude/skills/bike-finder/bike_finder.py
```

## Dependencies

```bash
pip install requests beautifulsoup4 playwright
playwright install chromium
```

Facebook Marketplace requires a one-time login setup:
```bash
python ~/.claude/skills/bike-finder/bike_finder.py --setup-fb
```
Session saved to `~/.config/bike-finder/fb-session.json`. Only needed once.

## Inputs to Collect from Dave

Before running, confirm:

| Input | Flag | Default | Example |
|-------|------|---------|---------|
| City | `--city` | vancouver | seattle, toronto |
| Budget (max $) | `--budget` | 500 | 400 |
| Bike type | `--type` | commuter | hybrid, road, mountain, gravel |
| Skip Facebook? | `--skip-fb` | false | use if no FB session |
| Min price | `--min-price` | 50 | 100 |

## Commands

**Full search (Craigslist + Facebook):**
```bash
python ~/.claude/skills/bike-finder/bike_finder.py \
  --city vancouver --budget 500 --type commuter
```

**Craigslist only (no FB session needed):**
```bash
python ~/.claude/skills/bike-finder/bike_finder.py \
  --city seattle --budget 400 --type hybrid --skip-fb
```

**Reddit research only:**
```bash
python ~/.claude/skills/bike-finder/bike_finder.py \
  --research-only --type commuter --budget 500
```

**Custom search query:**
```bash
python ~/.claude/skills/bike-finder/bike_finder.py \
  --city vancouver --budget 600 --query "trek hybrid commuter"
```

**JSON output (for programmatic use):**
```bash
python ~/.claude/skills/bike-finder/bike_finder.py \
  --city portland --budget 350 --output json
```

## What the Tool Does

1. Searches r/bikecommuting, r/cycling, r/whichbike for brand mentions and buying advice relevant to the bike type + budget
2. Builds a search query from top Reddit-mentioned brands + bike type
3. Scrapes Craigslist (handles both old and new layout) and optionally Facebook Marketplace
4. Scores each listing: +30 brand match, up to +25 price value, +4/keyword for condition words, -20/keyword for red flags (parts only, broken, needs work)
5. Outputs a ranked markdown table with links + top Reddit threads

## Presenting Results

Pipe output directly to Dave — the markdown table format is ready to display. For follow-up questions ("show me only Trek listings"), re-run with `--query "trek commuter"`.
