# bike-advisor

An OpenClaw skill that finds the best used bikes for sale in your city. Uses Reddit to identify top brands and buying criteria, then searches Craigslist and Facebook Marketplace, scoring and ranking results.

## Install

```bash
git clone https://github.com/daweezy13/bike-advisor ~/.openclaw/skills/bike-advisor
pip install requests beautifulsoup4 playwright
playwright install chromium
```

For Facebook Marketplace support, run the one-time login setup:
```bash
python ~/.openclaw/skills/bike-advisor/bike_finder.py --setup-fb
```

## Usage

Tell your agent: *"Find me a used commuter bike in Vancouver under $500"*

Or run directly:
```bash
python ~/.openclaw/skills/bike-advisor/bike_finder.py --city vancouver --budget 500 --type commuter
```

| Flag | Default | Options |
|------|---------|---------|
| `--city` | vancouver | Any Craigslist city |
| `--budget` | 500 | Max price in $ |
| `--type` | commuter | hybrid, road, mountain, gravel |
| `--min-price` | 50 | Filters spam/junk |
| `--skip-fb` | false | Craigslist only |
| `--research-only` | false | Reddit research, no listings |
| `--output` | markdown | markdown, json |

## How It Works

1. Searches Reddit (r/bikecommuting, r/cycling, r/whichbike) for brand recommendations matching your type and budget
2. Queries Craigslist and optionally Facebook Marketplace using Reddit-informed search terms
3. Scores listings by brand match, price value, and condition keywords
4. Returns a ranked table with links
