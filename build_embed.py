"""Update the demo HTML for a Yelp business."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REVIEWS_PATH = ROOT / "yelp-reviews.json"
WIDGET_HTML = ROOT / "public" / "reviwo-widget.html"
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
    <script src="embed.js" async></script>
    <div class="mdg-yelp-widget"
         data-yelp="__YELP_URL__"
         data-height="480"></div>
</body>

</html>
"""


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

    print(f"Updated reviwo-widget.html for {yelp_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
