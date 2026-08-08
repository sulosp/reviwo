"""Local dev server for the Yelp reviews widget.

Run:  python yelp-server.py
Open: http://localhost:8787/reviwo-widget.html

Deploy to Vercel (production):
  Connect this repo to Vercel — no Root Directory override needed.

Embed on any external site:
  <script src="https://YOUR-PROJECT.vercel.app/embed.js" async></script>
  <div class="mdg-yelp-widget"
       data-yelp="https://www.yelp.com/biz/YOUR-BUSINESS"
       data-height="480"></div>
"""

from __future__ import annotations

import json
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from yelp_fetch import (
    ROOT,
    fetch_yelp_reviews,
    load_cached_reviews,
)


class YelpHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / "public"), **kwargs)

    def end_headers(self):
        path = urlparse(self.path).path
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        if path in ("/embed.html", "/embed.js", "/widget.js", "/widget.css"):
            self.send_header("Content-Security-Policy", "frame-ancestors *")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/yelp-reviews":
            self.handle_reviews()
            return
        super().do_GET()

    def handle_reviews(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        yelp_url = (qs.get("yelp") or [None])[0]

        if not yelp_url:
            body = json.dumps(
                {
                    "error": (
                        "Missing required query param: "
                        "yelp=https://www.yelp.com/biz/your-business"
                    )
                }
            ).encode("utf-8")
            self.send_response(400)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)
            return

        try:
            payload = fetch_yelp_reviews(yelp_url=yelp_url)
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "public, max-age=300")
            self.end_headers()
            self.wfile.write(body)
        except Exception as exc:
            cached = load_cached_reviews(yelp_url)
            if cached:
                body = json.dumps(cached, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "public, max-age=300")
                self.end_headers()
                self.wfile.write(body)
                print(f"Served cached reviews after live fetch failed: {exc}", file=sys.stderr)
                return

            message = str(exc)
            body = json.dumps({"error": message}).encode("utf-8")
            self.send_response(502)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)
            print(f"Review fetch failed: {message}", file=sys.stderr)

    def log_message(self, format, *args):
        if args and isinstance(args[0], str) and "200" in str(args):
            return
        super().log_message(format, *args)


def main() -> None:
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8787"))
    public_url = os.environ.get("PUBLIC_URL", f"http://localhost:{port}")

    server = ThreadingHTTPServer((host, port), YelpHandler)
    print(f"Local dev:    {public_url}/reviwo-widget.html")
    print(f"Embed script: {public_url}/embed.js")
    print(f"Reviews API:  {public_url}/api/yelp-reviews?yelp=...")
    print(f"\nDeploy: connect this repo to Vercel and push to GitHub.")
    print("\nPaste into external site editor:")
    print(f'<script src="https://YOUR-PROJECT.vercel.app/embed.js" async></script>')
    print(
        '<div class="mdg-yelp-widget" data-yelp="https://www.yelp.com/biz/YOUR-BUSINESS" '
        'data-height="480"></div>'
    )

    if not os.environ.get("YELP_API_KEY"):
        print("\nWARNING: YELP_API_KEY is not set. Reviews for new data-yelp URLs will fail.", file=sys.stderr)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
