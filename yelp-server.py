"""Local dev server for the Yelp reviews widget.

Run:  python yelp-server.py
Open: http://localhost:8787/elfsight-widget.html

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
    REVIEWS_JSON_PATH,
    fetch_yelp_reviews,
    load_cached_reviews,
    slug_from_yelp_url,
)


def export_reviews_json(yelp_url: str | None = None) -> None:
    try:
        payload = fetch_yelp_reviews(yelp_url=yelp_url)
        REVIEWS_JSON_PATH.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"Exported {len(payload.get('reviews', []))} reviews to yelp-reviews.json")

        build_script = ROOT / "build_embed.py"
        if build_script.exists():
            import subprocess

            subprocess.run([sys.executable, str(build_script)], check=False)
    except Exception as exc:
        print(f"Could not export yelp-reviews.json: {exc}", file=sys.stderr)


def export_all_businesses() -> int:
    from yelp_fetch import load_businesses

    businesses = load_businesses()
    if not businesses:
        print("businesses.json is empty — exporting default business only.")
        try:
            export_reviews_json()
            return 0
        except Exception:
            return 1

    reviews_dir = ROOT / "reviews"
    reviews_dir.mkdir(exist_ok=True)
    failed = 0

    for slug, entry in businesses.items():
        yelp_url = entry.get("yelpUrl") or f"https://www.yelp.com/biz/{slug}"
        print(f"Fetching {slug} …")
        try:
            payload = fetch_yelp_reviews(yelp_url=yelp_url)
            out_path = reviews_dir / f"{slug}.json"
            out_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            count = len(payload.get("reviews", []))
            print(f"  → {count} reviews saved to reviews/{slug}.json")
        except Exception as exc:
            print(f"  → failed: {exc}", file=sys.stderr)
            failed += 1

    return failed


class YelpHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

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
    yelp_url = None
    if "--yelp" in sys.argv:
        idx = sys.argv.index("--yelp")
        if idx + 1 < len(sys.argv):
            yelp_url = sys.argv[idx + 1]

    if "--export-all" in sys.argv:
        raise SystemExit(export_all_businesses())

    if "--export" in sys.argv:
        export_reviews_json(yelp_url=yelp_url)
        return

    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8787"))
    public_url = os.environ.get("PUBLIC_URL", f"http://localhost:{port}")

    export_reviews_json(yelp_url=yelp_url)

    server = ThreadingHTTPServer((host, port), YelpHandler)
    print(f"Local dev:    {public_url}/elfsight-widget.html")
    print(f"Embed script: {public_url}/embed.js")
    print(f"Reviews API:  {public_url}/api/yelp-reviews?yelp=...")
    print(f"\nDeploy: connect this repo to Vercel and push to GitHub.")
    print("\nPaste into external site editor:")
    print(f'<script src="https://YOUR-PROJECT.vercel.app/embed.js" async></script>')
    print(
        '<div class="mdg-yelp-widget" data-yelp="https://www.yelp.com/biz/YOUR-BUSINESS" '
        'data-height="480"></div>'
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
