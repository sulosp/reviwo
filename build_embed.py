"""Update demo HTML and cache static review JSON for a Yelp business."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REVIEWS_PATH = ROOT / "yelp-reviews.json"
WIDGET_HTML = ROOT / "public" / "reviwo-widget.html"
REVIEWS_DIR = ROOT / "public" / "reviews"
DEFAULT_YELP_URL = "https://www.yelp.com/biz/mobile-dog-grooming-irvine-2"

WIDGET_TEMPLATE = """<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Yelp Reviews Widget</title>
    <link rel="stylesheet" href="widget.css">
</head>

<body>
    <div id="mdg-yelp-widget"></div>
    <script src="widget.js"></script>
    <script>
        var params = new URLSearchParams(window.location.search);
        MDG_YelpWidget.init(document.getElementById('mdg-yelp-widget'), {
            yelpUrl: params.get('yelp') || '__YELP_URL__',
            apiUrl: params.get('api') || (window.location.origin + '/api/yelp-reviews')
        });
    </script>
</body>

</html>
"""


def slug_from_source(source: str) -> str | None:
    match = re.search(r"/biz/([^/?#]+)", source or "")
    return match.group(1) if match else None


def main() -> int:
    if not REVIEWS_PATH.exists():
        print("Run: python yelp-server.py --export", file=sys.stderr)
        return 1

    data = json.loads(REVIEWS_PATH.read_text(encoding="utf-8"))
    yelp_url = data.get("source") or DEFAULT_YELP_URL

    WIDGET_HTML.write_text(
        WIDGET_TEMPLATE.replace("__YELP_URL__", yelp_url),
        encoding="utf-8",
    )

    slug = slug_from_source(yelp_url)
    if slug:
        REVIEWS_DIR.mkdir(exist_ok=True)
        slug_path = REVIEWS_DIR / f"{slug}.json"
        slug_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Cached static fallback to public/reviews/{slug}.json")

    print(f"Updated reviwo-widget.html for {yelp_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
