"""Vercel FastAPI entrypoint: static files from public/ + /api/yelp-reviews."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from yelp_fetch import fetch_yelp_reviews, load_cached_reviews  # noqa: E402

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/api/yelp-reviews")
def get_yelp_reviews(yelp: str = Query(..., description="Yelp business URL")):
    try:
        payload = fetch_yelp_reviews(yelp_url=yelp)
        return JSONResponse(
            content=payload,
            headers={"Cache-Control": "public, max-age=300"},
        )
    except Exception as exc:
        cached = load_cached_reviews(yelp)
        if cached:
            return JSONResponse(
                content=cached,
                headers={"Cache-Control": "public, max-age=300"},
            )
        raise HTTPException(status_code=502, detail=str(exc)) from exc
