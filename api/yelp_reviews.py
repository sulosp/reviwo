"""Vercel serverless handler: GET /api/yelp-reviews?yelp=https://www.yelp.com/biz/..."""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from yelp_fetch import fetch_yelp_reviews, load_cached_reviews  # noqa: E402

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


def write_json(handler: BaseHTTPRequestHandler, status: int, payload: dict, cache: bool = False):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    if cache:
        handler.send_header("Cache-Control", "public, max-age=300")
    for key, value in CORS_HEADERS.items():
        handler.send_header(key, value)
    handler.end_headers()
    handler.wfile.write(body)


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        for key, value in CORS_HEADERS.items():
            self.send_header(key, value)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        yelp_url = (qs.get("yelp") or [None])[0]

        if not yelp_url:
            write_json(
                self,
                400,
                {
                    "error": (
                        "Missing required query param: "
                        "yelp=https://www.yelp.com/biz/your-business"
                    )
                },
            )
            return

        try:
            payload = fetch_yelp_reviews(yelp_url=yelp_url)
            write_json(self, 200, payload, cache=True)
        except Exception as exc:
            cached = load_cached_reviews(yelp_url)
            if cached:
                write_json(self, 200, cached, cache=True)
                return
            write_json(self, 502, {"error": str(exc)})
