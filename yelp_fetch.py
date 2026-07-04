"""Yelp review fetching — shared by local server and Vercel serverless API."""

from __future__ import annotations

import json
import os
import re
from base64 import b64encode
from pathlib import Path

import requests

GQL_URL = "https://www.yelp.com/gql/batch"
DOC_ID = "ef51f33d1b0eccc958dddbf6cde15739c48b34637a00ebe316441031d4bf7681"
ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "yelp-config.json"
BUSINESSES_PATH = ROOT / "businesses.json"
REVIEWS_JSON_PATH = ROOT / "yelp-reviews.json"
REVIEWS_DIR = ROOT / "reviews"
DEFAULT_YELP_URL = "https://www.yelp.com/biz/mobile-dog-grooming-irvine-2"
DEFAULT_YELP_ALIAS = "mobile-dog-grooming-irvine-2"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def max_review_count() -> int:
    return int(os.environ.get("MAX_REVIEWS", "50" if os.environ.get("VERCEL") else "100"))


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def load_businesses() -> dict:
    if not BUSINESSES_PATH.exists():
        return {}
    try:
        return json.loads(BUSINESSES_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def slug_from_yelp_url(url: str) -> str | None:
    match = re.search(r"/biz/([^/?#]+)", url or "")
    return match.group(1) if match else None


def remember_business(yelp_url: str, biz_id: str) -> None:
    if os.environ.get("VERCEL"):
        return

    slug = slug_from_yelp_url(yelp_url)
    if not slug or not biz_id:
        return

    businesses = load_businesses()
    existing = businesses.get(slug) or {}
    if existing.get("bizId") == biz_id and existing.get("yelpUrl") == yelp_url:
        return

    try:
        businesses[slug] = {"bizId": biz_id, "yelpUrl": yelp_url}
        BUSINESSES_PATH.write_text(
            json.dumps(businesses, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass


def resolve_biz_id(yelp_url: str | None = None) -> str | None:
    if yelp_url:
        slug = slug_from_yelp_url(yelp_url)
        if slug:
            entry = load_businesses().get(slug) or {}
            if entry.get("bizId"):
                return str(entry["bizId"]).strip()
        return None

    if env_id := os.environ.get("YELP_BIZ_ID"):
        return env_id.strip()

    config = load_config()
    if config_id := config.get("bizId"):
        return str(config_id).strip()

    return None


def resolve_yelp_url(yelp_url: str | None = None) -> str:
    if yelp_url:
        return yelp_url.strip()
    return DEFAULT_YELP_URL


def extract_enc_biz_id(html: str, yelp_url: str | None = None) -> str | None:
    resolved = resolve_biz_id(yelp_url=yelp_url)
    if resolved:
        return resolved

    meta_match = re.search(
        r'<meta[^>]+name=["\']yelp-biz-id["\'][^>]+content=["\']([^"\']+)["\']',
        html,
        re.I,
    )
    if meta_match:
        return meta_match.group(1)

    for pattern in (
        r'"encid":"([^"]+)"',
        r'"encBizId":"([^"]+)"',
        r'"bizEncId":"([^"]+)"',
    ):
        if match := re.search(pattern, html):
            return match.group(1)
    return None


def fetch_page(session: requests.Session, yelp_url: str) -> requests.Response:
    return session.get(
        yelp_url,
        headers={
            **HEADERS,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://www.google.com/",
        },
        timeout=20,
    )


def fetch_reviews_page(
    session: requests.Session,
    enc_biz_id: str,
    yelp_url: str,
    offset: int = 0,
) -> dict:
    variables = {
        "encBizId": enc_biz_id,
        "reviewsPerPage": 10,
        "selectedReviewEncId": "",
        "hasSelectedReview": False,
        "sortBy": "DATE_DESC",
        "languageCode": "en",
        "ratings": [5, 4, 3, 2, 1],
        "isSearching": False,
        "isTranslating": False,
        "translateLanguageCode": "en",
        "reactionsSourceFlow": "businessPageReviewSection",
        "minConfidenceLevel": "HIGH_CONFIDENCE",
        "highlightType": "",
        "highlightIdentifier": "",
        "isHighlighting": False,
    }
    if offset:
        variables["after"] = b64encode(
            json.dumps({"version": 1, "type": "offset", "offset": offset}).encode()
        ).decode()

    payload = [
        {
            "operationName": "GetBusinessReviewFeed",
            "variables": variables,
            "extensions": {"operationType": "query", "documentId": DOC_ID},
        }
    ]

    response = session.post(
        GQL_URL,
        headers={
            **HEADERS,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Origin": "https://www.yelp.com",
            "Referer": yelp_url,
            "x-apollo-operation-name": "GetBusinessReviewFeed",
        },
        json=payload,
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()
    return data[0] if isinstance(data, list) else data


def format_review_date(node: dict) -> str:
    created = node.get("createdAt") or {}
    raw = (
        node.get("localizedDate")
        or created.get("localDateTimeForReview")
        or created.get("utcDateTime")
        or ""
    )
    if not raw:
        return ""
    if "T" in raw:
        return raw.split("T")[0]
    return raw


def extract_avatar_url(author: dict) -> str | None:
    photo = author.get("profilePhoto") or {}
    photo_url_obj = photo.get("photoUrl") or {}
    return (
        photo_url_obj.get("userSrc")
        or photo_url_obj.get("mediaItemSrcSetUrl200x")
        or photo_url_obj.get("url")
    )


def extract_review_images(node: dict) -> list[str]:
    images = []
    for photo in node.get("businessPhotos") or []:
        url_obj = photo.get("photoUrl") or {}
        url = (
            url_obj.get("url")
            or url_obj.get("url300x")
            or url_obj.get("url200x")
        )
        if url:
            images.append(url)
    return images


def parse_gql_reviews(data: dict) -> tuple[list[dict], float | None, int | None]:
    business = (data.get("data") or {}).get("business") or {}
    rating = business.get("rating")
    review_count = business.get("reviewCount")

    reviews = []
    edges = (business.get("reviews") or {}).get("edges") or []

    for edge in edges:
        node = edge.get("node") or {}
        author = node.get("author") or {}
        text = node.get("text") or {}
        name = author.get("displayName") or "Yelp User"
        reviews.append(
            {
                "name": name,
                "initial": name.strip()[0].upper() if name.strip() else "?",
                "date": format_review_date(node),
                "rating": node.get("rating") or 5,
                "text": text.get("full") or text.get("translated") or "",
                "photoUrl": extract_avatar_url(author),
                "images": extract_review_images(node),
            }
        )

    return reviews, rating, review_count


def fetch_via_fusion(session: requests.Session, yelp_url: str) -> dict:
    api_key = os.environ.get("YELP_API_KEY")
    if not api_key:
        raise RuntimeError("Yelp page blocked and YELP_API_KEY is not set")

    alias = slug_from_yelp_url(yelp_url) or DEFAULT_YELP_ALIAS
    headers = {"Authorization": f"Bearer {api_key}"}
    biz = session.get(
        f"https://api.yelp.com/v3/businesses/{alias}",
        headers=headers,
        timeout=20,
    )
    biz.raise_for_status()
    biz_data = biz.json()

    rev = session.get(
        f"https://api.yelp.com/v3/businesses/{alias}/reviews",
        headers=headers,
        timeout=20,
    )
    rev.raise_for_status()
    rev_data = rev.json()

    reviews = []
    for item in rev_data.get("reviews") or []:
        user = item.get("user") or {}
        name = user.get("name") or "Yelp User"
        reviews.append(
            {
                "name": name,
                "initial": name.strip()[0].upper() if name.strip() else "?",
                "date": item.get("time_created", "")[:10],
                "rating": item.get("rating") or 5,
                "text": item.get("text") or "",
                "photoUrl": user.get("image_url"),
                "images": [],
            }
        )

    return {
        "source": yelp_url,
        "rating": biz_data.get("rating"),
        "reviewCount": biz_data.get("review_count"),
        "reviews": reviews,
    }


def load_cached_reviews(yelp_url: str) -> dict | None:
    slug = slug_from_yelp_url(yelp_url)
    if slug:
        slug_path = REVIEWS_DIR / f"{slug}.json"
        if slug_path.exists():
            return json.loads(slug_path.read_text(encoding="utf-8"))
    if REVIEWS_JSON_PATH.exists():
        data = json.loads(REVIEWS_JSON_PATH.read_text(encoding="utf-8"))
        if data.get("source") == yelp_url:
            return data
    return None


def fetch_yelp_reviews(yelp_url: str | None = None) -> dict:
    session = requests.Session()
    yelp_url = resolve_yelp_url(yelp_url)
    enc_biz_id = resolve_biz_id(yelp_url)
    limit = max_review_count()

    if enc_biz_id:
        remember_business(yelp_url, enc_biz_id)
        all_reviews: list[dict] = []
        rating = None
        review_count = None

        for offset in range(0, limit, 10):
            data = fetch_reviews_page(session, enc_biz_id, yelp_url, offset)
            batch, rating, review_count = parse_gql_reviews(data)
            if not batch:
                break
            all_reviews.extend(batch)
            if len(batch) < 10:
                break

        if all_reviews:
            return {
                "source": yelp_url,
                "rating": rating,
                "reviewCount": review_count,
                "reviews": all_reviews,
            }

    page = fetch_page(session, yelp_url)

    if page.status_code == 403:
        slug = slug_from_yelp_url(yelp_url) or "your-business"
        raise RuntimeError(
            f"Yelp blocked the server request for {yelp_url}. "
            f"Add the business to businesses.json: "
            f'{{"{slug}": {{"bizId": "YOUR_ID", "yelpUrl": "{yelp_url}"}}}}.'
        )

    page.raise_for_status()
    enc_biz_id = extract_enc_biz_id(page.text, yelp_url)
    if not enc_biz_id:
        slug = slug_from_yelp_url(yelp_url) or "your-business"
        raise RuntimeError(
            f"Could not find yelp-biz-id for {yelp_url}. Add it to businesses.json: "
            f'{{"{slug}": {{"bizId": "YOUR_ID", "yelpUrl": "{yelp_url}"}}}}.'
        )

    remember_business(yelp_url, enc_biz_id)

    all_reviews = []
    rating = None
    review_count = None

    for offset in range(0, limit, 10):
        data = fetch_reviews_page(session, enc_biz_id, yelp_url, offset)
        batch, rating, review_count = parse_gql_reviews(data)
        if not batch:
            break
        all_reviews.extend(batch)
        if len(batch) < 10:
            break

    if not all_reviews:
        return fetch_via_fusion(session, yelp_url)

    return {
        "source": yelp_url,
        "rating": rating,
        "reviewCount": review_count,
        "reviews": all_reviews,
    }
