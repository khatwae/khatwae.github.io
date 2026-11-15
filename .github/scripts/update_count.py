#!/usr/bin/env python3
"""بلّط البحر — check the YouTube subscriber count and update count.json.

Runs in GitHub Actions every 10 minutes. Reads the PUBLIC channel page
(no API key needed while the count is below 1,000 and YouTube shows it
exactly). Rules:
- Only ever RAISES the count (a placed tile is never removed).
- If the number is abbreviated (1.2K / 1.2 ألف) or cannot be parsed,
  exit 0 WITHOUT changing anything — never guess.
- Network errors: log and exit 0 without changes.
"""
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone

CHANNEL = "https://www.youtube.com/@ballat.albahr"
COUNT_PATH = "ballat-albahr/count.json"
MAX_TILES = 10000

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def parse_count(html):
    """Extract the exact subscriber number from the channel header.

    Current YouTube header structure (verified 2026-11-15 on the live page):
      English: "content":"2 subscribers"   (metadataParts, next to "1 video")
      Arabic:  "content":"مشتركان (2)"     (same spot, number in parentheses)
    Older structure kept as fallback: subscriberCountText.simpleText.
    Returns an int, or None when absent/abbreviated/unparseable.
    """
    # Scan the header's "content" values in page order; the first value
    # that parses as an exact subscriber count is the channel's.
    for m in re.finditer(r"\"content\":\"([^\"]+)\"", html):
        text = m.group(1).strip()
        n = parse_count_text(text)
        if n is not None:
            return n
    # Fallback: older subscriberCountText structure.
    m = re.search(r"subscriberCountText.{0,600}?\"simpleText\":\"([^\"]+)\"",
                  html, re.DOTALL)
    if m:
        return parse_count_text(m.group(1).strip())
    m = re.search(r"subscriberCountText.{0,600}?\"label\":\"([^\"]+)\"",
                  html, re.DOTALL)
    if m:
        return parse_count_text(m.group(1).strip())
    return None


def parse_count_text(text):
    """Parse one candidate string; None when abbreviated/unparseable."""
    # Abbreviated counts (YouTube shortens from ~1,000 up) — never guess.
    if re.search(r"[KMk]\b|ألف|مليون|مليار", text):
        return None
    if re.search(r"\d\.\d", text):  # e.g. "1.2K subscribers"
        return None
    # English: "2 subscribers" / "1 subscriber"
    m = re.match(r"^([\d,]+)\s+subscribers?$", text)
    if m:
        return int(m.group(1).replace(",", ""))
    # Arabic: number in parentheses, e.g. "مشتركان (2)"
    m = re.search(r"\(([\d,]+)\)", text)
    if m:
        return int(m.group(1).replace(",", ""))
    # Arabic singular: "مشترك واحد" = 1
    if text == "مشترك واحد":
        return 1
    return None


def main():
    html = None
    for url in (CHANNEL + "?hl=en", CHANNEL + "/about?hl=en",
                CHANNEL + "?hl=ar", CHANNEL + "/about?hl=ar"):
        try:
            html = fetch(url)
        except Exception as e:
            print(f"fetch failed for {url}: {e}")
            continue
        count = parse_count(html)
        if count is not None:
            break
        print(f"no parseable count on {url}")
    else:
        print("could not read an exact subscriber count; leaving count.json untouched")
        return 0

    if not (0 <= count <= MAX_TILES):
        print(f"implausible count {count}; leaving count.json untouched")
        return 0

    try:
        with open(COUNT_PATH) as f:
            current = json.load(f).get("count", 0)
    except Exception as e:
        print(f"cannot read {COUNT_PATH}: {e}; leaving it untouched")
        return 0

    if count <= current:
        print(f"subscribers={count}, current count.json={current}: no change")
        return 0

    data = {
        "count": count,
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    with open(COUNT_PATH, "w") as f:
        json.dump(data, f, ensure_ascii=False)
        f.write("\n")
    print(f"updated {COUNT_PATH}: {current} -> {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
