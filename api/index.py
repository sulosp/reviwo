"""Vercel FastAPI entrypoint: static files from public/ + /api/yelp-reviews."""

from __future__ import annotations

import json
import sys
import time
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


def _debug_log(message: str, data: dict, hypothesis_id: str = "H1") -> None:
    # #region agent log
    try:
        log_path = ROOT / "debug-cd155e.log"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "sessionId": "cd155e",
                        "hypothesisId": hypothesis_id,
                        "location": "api/index.py",
                        "message": message,
                        "data": data,
                        "timestamp": int(time.time() * 1000),
                    }
                )
                + "\n"
            )
    except Exception:
        pass
    # #endregion


@app.get("/api/yelp-reviews")
def get_yelp_reviews(yelp: str = Query(..., description="Yelp business URL")):
    _debug_log("API route hit", {"yelp": yelp, "hasYelp": True}, "H6")

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
