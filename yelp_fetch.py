"""Yelp review fetching — shared by local server and Vercel serverless API.

With a standard Yelp Places (Fusion) key:
  - Base plan: business details only (no review excerpts) → GQL fallback
  - Enhanced+: GET /v3/businesses/{id}/reviews → up to 3 excerpts
  - Private Reviews API: partner-only; tried when enabled, then ignored on 403

Widget embeds are intentionally capped at 3 reviews.
"""

from __future__ import annotations

import json
import os
import re
from base64 import b64encode
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests

GQL_URL = "https://www.yelp.com/gql/batch"
DOC_ID = "ef51f33d1b0eccc958dddbf6cde15739c48b34637a00ebe316441031d4bf7681"
ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "yelp-config.json"
BUSINESSES_PATH = ROOT / "businesses.json"
REVIEWS_JSON_PATH = ROOT / "yelp-reviews.json"
REVIEWS_DIR = ROOT / "public" / "reviews"
DEFAULT_YELP_URL = "https://www.yelp.com/biz/mobile-dog-grooming-irvine-2"
DEFAULT_YELP_ALIAS = "mobile-dog-grooming-irvine-2"
DEFAULT_MAX_REVIEWS = 3


def load_local_env() -> None:
    for env_path in (ROOT / ".env", ROOT / ".env.local"):
        if not env_path.exists():
            continue

        try:
            for raw_line in env_path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[7:].strip()
                if "=" not in line:
                    continue

                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
        except OSError:
            pass


load_local_env()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def max_review_count() -> int:
    raw = os.environ.get("MAX_REVIEWS", str(DEFAULT_MAX_REVIEWS))
    try:
        return max(1, min(int(raw), 3))
    except ValueError:
        return DEFAULT_MAX_REVIEWS


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
    match = re.search(r"/biz/([^/?#]+)", url or "", re.I)
    if not match:
        return None
    return unquote(match.group(1)).strip().rstrip("/")


def normalize_yelp_url(url: str) -> str:
    """Accept full Yelp biz URLs (with query/hash) and return a clean /biz/{slug} URL."""
    raw = (url or "").strip()
    if not raw:
        raise ValueError("Yelp URL is empty")

    if "://" not in raw and raw.startswith("www."):
        raw = "https://" + raw
    if "://" not in raw and "/" not in raw:
        raw = f"https://www.yelp.com/biz/{raw}"

    parsed = urlparse(raw)
    host = (parsed.netloc or "").lower()
    if host and "yelp." not in host:
        raise ValueError(f"Not a Yelp business URL: {url}")

    slug = slug_from_yelp_url(raw)
    if not slug:
        raise ValueError(
            "Could not find a /biz/… slug in data-yelp. "
            "Use a full URL like https://www.yelp.com/biz/your-business-name"
        )
    return f"https://www.yelp.com/biz/{slug}"


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
        return normalize_yelp_url(yelp_url)
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


def api_headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}


def fetch_business_details(session: requests.Session, yelp_url: str) -> dict | None:
    """Resolve a business via Fusion Business Details (available on Base)."""
    api_key = os.environ.get("YELP_API_KEY")
    if not api_key:
        return None

    alias = slug_from_yelp_url(yelp_url)
    if not alias:
        return None

    response = session.get(
        f"https://api.yelp.com/v3/businesses/{alias}",
        headers=api_headers(api_key),
        timeout=20,
    )
    if response.status_code == 404:
        return None
    if not response.ok:
        raise RuntimeError(
            f"Yelp business lookup failed ({response.status_code}): "
            f"{_yelp_error_text(response)}"
        )

    data = response.json()
    business_id = str(data.get("id") or "").strip()
    business_alias = str(data.get("alias") or alias).strip()
    if not business_id:
        return None

    return {
        "id": business_id,
        "alias": business_alias,
        "rating": data.get("rating"),
        "review_count": data.get("review_count"),
        "url": data.get("url") or f"https://www.yelp.com/biz/{business_alias}",
        "name": data.get("name"),
    }


def _yelp_error_text(response: requests.Response) -> str:
    try:
        payload = response.json()
        err = payload.get("error") or {}
        if isinstance(err, dict):
            return err.get("description") or err.get("code") or response.text[:200]
        return str(err) or response.text[:200]
    except Exception:
        return response.text[:200] or response.reason


def lookup_biz_id_via_fusion(session: requests.Session, yelp_url: str) -> str | None:
    details = fetch_business_details(session, yelp_url)
    return details["id"] if details else None


def resolve_enc_biz_id(session: requests.Session, yelp_url: str) -> str | None:
    if enc_biz_id := resolve_biz_id(yelp_url):
        return enc_biz_id

    if enc_biz_id := lookup_biz_id_via_fusion(session, yelp_url):
        return enc_biz_id

    page = fetch_page(session, yelp_url)
    if page.status_code == 403:
        return None
    page.raise_for_status()
    return extract_enc_biz_id(page.text, yelp_url)


def fetch_reviews_page(
    session: requests.Session,
    enc_biz_id: str,
    yelp_url: str,
    offset: int = 0,
    reviews_per_page: int = 10,
) -> dict:
    variables = {
        "encBizId": enc_biz_id,
        "reviewsPerPage": reviews_per_page,
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


def fetch_reviews_via_gql(
    session: requests.Session,
    enc_biz_id: str,
    yelp_url: str,
    limit: int | None = None,
) -> dict | None:
    limit = limit or max_review_count()
    all_reviews: list[dict] = []
    rating = None
    review_count = None
    page_size = min(10, limit)

    for offset in range(0, limit, page_size):
        data = fetch_reviews_page(
            session, enc_biz_id, yelp_url, offset, reviews_per_page=page_size
        )
        batch, rating, review_count = parse_gql_reviews(data)
        if not batch:
            break
        all_reviews.extend(batch)
        if len(all_reviews) >= limit or len(batch) < page_size:
            break

    if not all_reviews:
        return None

    return {
        "source": yelp_url,
        "rating": rating,
        "reviewCount": review_count,
        "reviews": all_reviews[:limit],
    }


def _normalize_review(
    *,
    name: str,
    date: str,
    rating: int | float | None,
    text: str,
    photo_url: str | None,
    images: list[str] | None = None,
) -> dict:
    clean_name = name or "Yelp User"
    return {
        "name": clean_name,
        "initial": clean_name.strip()[0].upper() if clean_name.strip() else "?",
        "date": date,
        "rating": rating or 5,
        "text": text or "",
        "photoUrl": photo_url,
        "images": images or [],
    }


def fetch_via_fusion(session: requests.Session, yelp_url: str, biz: dict | None = None) -> dict:
    """Fusion Reviews API — up to 3 excerpts (Enhanced+ plans)."""
    api_key = os.environ.get("YELP_API_KEY")
    if not api_key:
        raise RuntimeError("YELP_API_KEY is not set")

    biz = biz or fetch_business_details(session, yelp_url)
    if not biz:
        raise RuntimeError(f"Yelp business not found for {yelp_url}")

    headers = api_headers(api_key)
    identifiers = [biz["alias"], biz["id"]]
    rev = None
    last_status = None

    for ident in identifiers:
        candidate = session.get(
            f"https://api.yelp.com/v3/businesses/{ident}/reviews",
            headers=headers,
            params={"locale": "en_US", "limit": max_review_count()},
            timeout=20,
        )
        last_status = candidate.status_code
        if candidate.ok:
            rev = candidate
            break
        if candidate.status_code not in (404, 403):
            raise RuntimeError(
                f"Yelp reviews API failed ({candidate.status_code}): "
                f"{_yelp_error_text(candidate)}"
            )

    if rev is None:
        raise RuntimeError(
            "Yelp Fusion Reviews API returned "
            f"{last_status} (no review excerpts on this API plan). "
            "Base plans do not include review excerpts — Enhanced includes up to 3. "
            "See https://docs.developer.yelp.com/docs/plans"
        )

    rev_data = rev.json()
    reviews = []
    for item in rev_data.get("reviews") or []:
        user = item.get("user") or {}
        reviews.append(
            _normalize_review(
                name=user.get("name") or "Yelp User",
                date=(item.get("time_created") or "")[:10],
                rating=item.get("rating") or 5,
                text=item.get("text") or "",
                photo_url=user.get("image_url"),
            )
        )

    return {
        "source": yelp_url,
        "rating": biz.get("rating"),
        "reviewCount": biz.get("review_count") or rev_data.get("total") or len(reviews),
        "reviews": reviews[: max_review_count()],
        "provider": "fusion",
    }


def fetch_via_private_reviews(
    session: requests.Session, yelp_url: str, biz: dict | None = None
) -> dict:
    """Private Reviews API — partner access only.

    Docs: https://docs.developer.yelp.com/docs/private-reviews-api
    """
    api_key = os.environ.get("YELP_API_KEY")
    if not api_key:
        raise RuntimeError("YELP_API_KEY is not set")

    biz = biz or fetch_business_details(session, yelp_url)
    if not biz:
        raise RuntimeError(f"Yelp business not found for {yelp_url}")

    response = session.get(
        f"https://api.yelp.com/v3/private/businesses/{biz['id']}/reviews",
        headers=api_headers(api_key),
        params={"locale": "en_US"},
        timeout=20,
    )
    if response.status_code in (401, 403):
        raise RuntimeError(
            "Yelp Private Reviews API is not enabled for this key "
            "(partner API — access disabled by default). "
            "See https://docs.developer.yelp.com/docs/private-reviews-api"
        )
    if response.status_code == 404:
        # Some partner setups accept alias instead of id.
        response = session.get(
            f"https://api.yelp.com/v3/private/businesses/{biz['alias']}/reviews",
            headers=api_headers(api_key),
            params={"locale": "en_US"},
            timeout=20,
        )
    if not response.ok:
        raise RuntimeError(
            f"Yelp Private Reviews API failed ({response.status_code}): "
            f"{_yelp_error_text(response)}"
        )

    payload = response.json()
    raw_reviews = payload.get("reviews")
    if isinstance(raw_reviews, dict):
        items = raw_reviews.get("review") or []
    elif isinstance(raw_reviews, list):
        items = raw_reviews
    else:
        items = []

    reviews = []
    for item in items:
        user = item.get("user") or {}
        time_created = item.get("time_created") or ""
        date = time_created[:10].replace(" ", "T").split("T")[0]
        reviews.append(
            _normalize_review(
                name=user.get("name") or "Yelp User",
                date=date,
                rating=item.get("rating") or 5,
                text=item.get("text") or "",
                photo_url=user.get("image_url"),
            )
        )

    if not reviews:
        raise RuntimeError("Yelp Private Reviews API returned no reviews")

    return {
        "source": yelp_url,
        "rating": biz.get("rating"),
        "reviewCount": biz.get("review_count") or len(reviews),
        "reviews": reviews[: max_review_count()],
        "provider": "private",
    }


def biz_id_error_message(yelp_url: str) -> str:
    slug = slug_from_yelp_url(yelp_url) or "your-business"
    return (
        f"Could not load reviews for {yelp_url}. "
        f"Set YELP_API_KEY (Enhanced+ for official 3 excerpts), or add the business to "
        f'businesses.json: {{"{slug}": {{"bizId": "YOUR_ID", "yelpUrl": "{yelp_url}"}}}}. '
        f"Find YOUR_ID in the Yelp page source (search for yelp-biz-id)."
    )


def load_cached_reviews(yelp_url: str) -> dict | None:
    slug = slug_from_yelp_url(yelp_url)
    if slug:
        slug_path = REVIEWS_DIR / f"{slug}.json"
        if slug_path.exists():
            return _cap_payload(json.loads(slug_path.read_text(encoding="utf-8")))
    if REVIEWS_JSON_PATH.exists():
        data = json.loads(REVIEWS_JSON_PATH.read_text(encoding="utf-8"))
        if data.get("source") == yelp_url or slug_from_yelp_url(data.get("source") or "") == slug:
            return _cap_payload(data)
    return None


def _cap_payload(payload: dict) -> dict:
    limit = max_review_count()
    reviews = list(payload.get("reviews") or [])[:limit]
    capped = dict(payload)
    capped["reviews"] = reviews
    return capped


def _with_business_meta(payload: dict, biz: dict | None) -> dict:
    if not biz:
        return _cap_payload(payload)
    merged = dict(payload)
    if merged.get("rating") is None and biz.get("rating") is not None:
        merged["rating"] = biz.get("rating")
    if not merged.get("reviewCount") and biz.get("review_count") is not None:
        merged["reviewCount"] = biz.get("review_count")
    return _cap_payload(merged)


def fetch_yelp_reviews(yelp_url: str | None = None) -> dict:
    session = requests.Session()
    try:
        yelp_url = resolve_yelp_url(yelp_url)
    except ValueError as exc:
        raise RuntimeError(str(exc)) from exc

    errors: list[str] = []
    biz = None

    if os.environ.get("YELP_API_KEY"):
        try:
            biz = fetch_business_details(session, yelp_url)
        except Exception as exc:
            errors.append(f"business lookup: {exc}")

        if biz:
            remember_business(yelp_url, biz["id"])
            # Prefer canonical alias URL when Fusion redirects (slug mismatches).
            canonical = f"https://www.yelp.com/biz/{biz['alias']}"
            if slug_from_yelp_url(yelp_url) != biz["alias"]:
                yelp_url = canonical

            # 1) Official Fusion reviews (Enhanced+: up to 3 excerpts)
            try:
                return _with_business_meta(fetch_via_fusion(session, yelp_url, biz=biz), biz)
            except Exception as exc:
                errors.append(str(exc))

            # 2) Private Reviews partner API (full text when contracted)
            try:
                return _with_business_meta(
                    fetch_via_private_reviews(session, yelp_url, biz=biz), biz
                )
            except Exception as exc:
                errors.append(str(exc))
        elif not errors:
            errors.append(
                f"Yelp business not found for {yelp_url}. "
                "Check that data-yelp is a valid https://www.yelp.com/biz/… URL."
            )

    # 3) GraphQL page feed (works without review-API plan access)
    enc_biz_id = (biz or {}).get("id") if biz else None
    if not enc_biz_id:
        try:
            enc_biz_id = resolve_enc_biz_id(session, yelp_url)
        except Exception as exc:
            errors.append(f"biz id resolve: {exc}")

    if enc_biz_id:
        remember_business(yelp_url, enc_biz_id)
        try:
            if payload := fetch_reviews_via_gql(session, enc_biz_id, yelp_url):
                return _with_business_meta(payload, biz)
            errors.append("Yelp review feed returned no reviews")
        except Exception as exc:
            errors.append(f"review feed: {exc}")

    detail = "; ".join(errors) if errors else biz_id_error_message(yelp_url)
    raise RuntimeError(detail)
