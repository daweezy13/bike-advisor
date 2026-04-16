#!/usr/bin/env python3
"""
bike-finder — Reddit research + Craigslist/Facebook Marketplace search for used bikes

Usage:
  python bike_finder.py --city vancouver --budget 500 --type commuter
  python bike_finder.py --setup-fb          # one-time FB login
  python bike_finder.py --research-only --type commuter --budget 400
  python bike_finder.py --skip-fb --city seattle --budget 300 --type hybrid
"""

import argparse
import json
import os
import re
import sys
import time
from collections import Counter

import requests
from bs4 import BeautifulSoup

# ── Config ────────────────────────────────────────────────────────────────────

REDDIT_UA = "bike-finder/1.0"
SESSION_FILE = os.path.expanduser("~/.config/bike-finder/fb-session.json")

BIKE_SUBS = ["bikecommuting", "cycling", "whichbike", "bicycling"]

BRANDS = [
    "trek", "giant", "specialized", "cannondale", "kona", "norco", "fuji",
    "schwinn", "raleigh", "marin", "surly", "jamis", "bianchi", "scott",
    "cube", "orbea", "gt", "diamondback", "felt", "cervelo", "salsa",
]

CRAIGSLIST_CITIES = {
    "vancouver": "vancouver",
    "toronto": "toronto",
    "calgary": "calgary",
    "edmonton": "edmonton",
    "ottawa": "ottawa",
    "montreal": "montreal",
    "seattle": "seattle",
    "portland": "portland",
    "sf": "sfbay",
    "san francisco": "sfbay",
    "los angeles": "losangeles",
    "new york": "newyork",
    "chicago": "chicago",
    "boston": "boston",
    "denver": "denver",
    "austin": "austin",
    "phoenix": "phoenix",
}

# ── Reddit research ───────────────────────────────────────────────────────────

def reddit_search(subreddit, query, limit=10, sort="top", timeframe="year"):
    url = f"https://www.reddit.com/r/{subreddit}/search.json"
    params = {"q": query, "restrict_sr": 1, "sort": sort, "t": timeframe, "limit": limit}
    r = requests.get(url, params=params, headers={"User-Agent": REDDIT_UA}, timeout=10)
    r.raise_for_status()
    return r.json().get("data", {}).get("children", [])


def extract_brands(text):
    text_lower = text.lower()
    return [b for b in BRANDS if b in text_lower]


def run_research(bike_type, budget):
    print(f"\n[1/3] Reddit research: {bike_type} bikes under ${budget}...")

    queries = [
        f"best {bike_type} bike under {budget}",
        f"{bike_type} bike recommendation used",
        f"what to look for used {bike_type} bike",
    ]

    all_posts = []
    brand_counter = Counter()
    red_flags = []

    for sub in BIKE_SUBS[:3]:
        for query in queries[:2]:
            try:
                posts = reddit_search(sub, query, limit=10)
                for post in posts:
                    d = post["data"]
                    text = d["title"] + " " + d.get("selftext", "")
                    brand_counter.update(extract_brands(text))
                    all_posts.append({
                        "title": d["title"],
                        "score": d["score"],
                        "text": d.get("selftext", "")[:300],
                        "url": f"https://reddit.com{d['permalink']}",
                    })
                time.sleep(0.6)
            except Exception as e:
                print(f"  Warning: r/{sub} failed — {e}", file=sys.stderr)

    top_brands = [b for b, _ in brand_counter.most_common(8) if brand_counter[b] > 1]
    top_posts = sorted(all_posts, key=lambda x: x["score"], reverse=True)[:5]

    print(f"  Top brands mentioned: {', '.join(top_brands[:6]) or 'varied'}")
    print(f"  Discussions found: {len(all_posts)}")

    return {
        "recommended_brands": top_brands,
        "top_discussions": top_posts,
    }


# ── Craigslist ────────────────────────────────────────────────────────────────

def search_craigslist(city, query, max_price, min_price=50):
    city_key = re.sub(r"[,\s]+.*", "", city.lower().strip())  # "vancouver, bc" → "vancouver"
    cl_city = CRAIGSLIST_CITIES.get(city_key, city_key)

    url = f"https://{cl_city}.craigslist.org/search/bia"
    params = {"query": query, "max_price": max_price, "min_price": min_price, "sort": "date"}

    try:
        r = requests.get(
            url, params=params,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
            timeout=15,
        )
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        listings = []

        for item in soup.select("li.cl-search-result, li.result-row")[:25]:
            # Support both new and legacy Craigslist layout
            title_el = (
                item.select_one("[data-testid='listing-title']")
                or item.select_one(".title")
                or item.select_one("a.cl-app-anchor span")
            )
            price_el = item.select_one(".priceinfo") or item.select_one(".price")
            link_el = item.select_one("a.cl-app-anchor") or item.select_one("a.result-title") or item.select_one("a")
            location_el = item.select_one(".location") or item.select_one(".result-hood")

            title = title_el.get_text(strip=True) if title_el else ""
            price = price_el.get_text(strip=True) if price_el else "N/A"
            href = link_el.get("href", "") if link_el else ""
            location = location_el.get_text(strip=True) if location_el else ""

            if not title:
                continue

            full_url = href if href.startswith("http") else f"https://{cl_city}.craigslist.org{href}"
            listings.append({
                "title": title,
                "price": price,
                "location": location,
                "url": full_url,
                "source": "craigslist",
            })

        return listings

    except Exception as e:
        print(f"  Craigslist failed: {e}", file=sys.stderr)
        return []


# ── Facebook Marketplace ──────────────────────────────────────────────────────

def setup_fb_session():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright not installed. Run:\n  pip install playwright && playwright install chromium")
        sys.exit(1)

    os.makedirs(os.path.dirname(SESSION_FILE), exist_ok=True)
    print("\nOpening browser for Facebook login...")
    print("Log in to your account, then come back here and press Enter.\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://www.facebook.com/login")
        input("Press Enter after logging in...")
        context.storage_state(path=SESSION_FILE)
        browser.close()

    print(f"\n✓ Session saved → {SESSION_FILE}")
    print("Future searches will use this session automatically.\n")


def search_facebook_marketplace(query, max_price, city=None):
    if not os.path.exists(SESSION_FILE):
        print("  FB Marketplace: no session. Run --setup-fb first.", file=sys.stderr)
        return []

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  FB Marketplace: playwright not installed.", file=sys.stderr)
        return []

    listings = []
    city_path = city.lower().replace(" ", "-").split(",")[0].strip() if city else "marketplace"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(storage_state=SESSION_FILE)
            page = context.new_page()

            encoded_query = requests.utils.quote(query)
            url = (
                f"https://www.facebook.com/marketplace/{city_path}/search/"
                f"?query={encoded_query}&maxPrice={max_price}&exact=false"
            )

            page.goto(url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(3000)

            for item in page.query_selector_all('a[href*="/marketplace/item/"]')[:25]:
                try:
                    href = item.get_attribute("href") or ""
                    spans = [s.inner_text() for s in item.query_selector_all("span") if s.inner_text().strip()]
                    title = next((t for t in spans if len(t) > 5 and "$" not in t and not t.isdigit()), "")
                    price = next((t for t in spans if "$" in t), "N/A")
                    if title:
                        listings.append({
                            "title": title,
                            "price": price,
                            "url": f"https://www.facebook.com{href}",
                            "source": "facebook_marketplace",
                        })
                except Exception:
                    continue

            browser.close()

    except Exception as e:
        print(f"  FB Marketplace failed: {e}", file=sys.stderr)

    return listings


# ── Scoring ───────────────────────────────────────────────────────────────────

POSITIVE_KW = ["commuter", "hybrid", "city", "road", "gravel", "shimano", "aluminum",
               "excellent", "like new", "barely used", "great condition", "light"]
NEGATIVE_KW = ["parts only", "for parts", "broken", "damaged", "project bike",
               "needs work", "as is", "cracked", "bent"]


def score_listing(listing, recommended_brands, max_price):
    score = 0
    title_lower = listing["title"].lower()

    # Brand match from Reddit research
    for brand in recommended_brands:
        if brand in title_lower:
            score += 30
            break

    # Price (lower is better, scaled within budget)
    try:
        price_val = float(re.sub(r"[^\d.]", "", str(listing.get("price", "0"))) or "0")
        if 50 < price_val <= max_price:
            score += int((1 - price_val / max_price) * 25)
    except Exception:
        pass

    for kw in POSITIVE_KW:
        if kw in title_lower:
            score += 4

    for kw in NEGATIVE_KW:
        if kw in title_lower:
            score -= 20

    return score


# ── Output ────────────────────────────────────────────────────────────────────

def format_markdown(research, listings, city, budget, bike_type):
    lines = [
        f"# Used {bike_type.title()} Bike Search — {city.title()} (max ${budget})\n",
    ]

    if research["recommended_brands"]:
        lines.append(f"**Reddit-recommended brands:** {', '.join(research['recommended_brands'][:6])}\n")

    if not listings:
        lines.append("No listings found. Try a different city spelling or broader query.\n")
        return "\n".join(lines)

    lines.append(f"**{len(listings)} listings found**, ranked by brand + price + condition:\n")
    lines.append("| # | Title | Price | Source | Link |")
    lines.append("|---|-------|-------|--------|------|")

    for i, l in enumerate(listings[:15], 1):
        title = (l["title"][:52] + "…") if len(l["title"]) > 52 else l["title"]
        price = l.get("price", "N/A")
        source = l["source"].replace("_", " ").title()
        lines.append(f"| {i} | {title} | {price} | {source} | [→]({l['url']}) |")

    if research["top_discussions"]:
        lines.append("\n## Reddit Reading\n")
        for post in research["top_discussions"][:3]:
            lines.append(f"- [{post['title']}]({post['url']}) ↑{post['score']}")

    return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Find used bikes via Reddit research + marketplace search",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--city", default="vancouver",
                        help="City name (e.g. vancouver, toronto, seattle)")
    parser.add_argument("--budget", type=int, default=500,
                        help="Max price in dollars")
    parser.add_argument("--min-price", type=int, default=50,
                        help="Min price — filters out junk/spam (default: 50)")
    parser.add_argument("--type", dest="bike_type", default="commuter",
                        help="Bike type: commuter, hybrid, road, mountain, gravel")
    parser.add_argument("--query", default=None,
                        help="Override search query (default: auto-built from type + Reddit brands)")
    parser.add_argument("--setup-fb", action="store_true",
                        help="One-time Facebook Marketplace login setup")
    parser.add_argument("--skip-fb", action="store_true",
                        help="Skip Facebook Marketplace, use Craigslist only")
    parser.add_argument("--research-only", action="store_true",
                        help="Reddit research only — no marketplace search")
    parser.add_argument("--output", choices=["markdown", "json"], default="markdown")

    args = parser.parse_args()

    if args.setup_fb:
        setup_fb_session()
        return

    # Phase 1: Reddit
    research = run_research(args.bike_type, args.budget)

    if args.research_only:
        print(f"\nTop brands: {', '.join(research['recommended_brands'])}")
        print("\nTop discussions:")
        for p in research["top_discussions"][:5]:
            print(f"  {p['score']:>5} ↑  {p['title']}")
            print(f"         {p['url']}")
        return

    # Build query
    brand_hints = " ".join(research["recommended_brands"][:2])
    query = args.query or f"{args.bike_type} bike {brand_hints}".strip()

    print(f"\n[2/3] Marketplace search: \"{query}\" in {args.city} (${args.min_price}–${args.budget})")

    all_listings = []

    # Craigslist
    cl = search_craigslist(args.city, query, args.budget, args.min_price)
    print(f"  Craigslist: {len(cl)} listings")
    all_listings.extend(cl)

    # Facebook Marketplace
    if not args.skip_fb:
        fb = search_facebook_marketplace(query, args.budget, args.city)
        print(f"  Facebook Marketplace: {len(fb)} listings")
        all_listings.extend(fb)

    # Phase 3: Score + rank
    print(f"\n[3/3] Scoring and ranking {len(all_listings)} listings...")
    for listing in all_listings:
        listing["score"] = score_listing(listing, research["recommended_brands"], args.budget)

    ranked = sorted(all_listings, key=lambda x: x.get("score", 0), reverse=True)

    if args.output == "json":
        print(json.dumps({"research": research, "listings": ranked[:20]}, indent=2))
    else:
        print("\n" + format_markdown(research, ranked, args.city, args.budget, args.bike_type))


if __name__ == "__main__":
    main()
