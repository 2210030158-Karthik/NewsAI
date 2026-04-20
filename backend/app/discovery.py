from typing import Any, Dict, List
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from serpapi import GoogleSearch

from .config import settings

# Tracking parameters are excluded to improve dedupe quality.
_TRACKING_PARAM_PREFIXES = ("utm_",)
_TRACKING_PARAM_EXACT = {"gclid", "fbclid", "mc_cid", "mc_eid", "ref"}


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    clean_query = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        key_lower = key.lower()
        if key_lower in _TRACKING_PARAM_EXACT:
            continue
        if any(key_lower.startswith(prefix) for prefix in _TRACKING_PARAM_PREFIXES):
            continue
        clean_query.append((key, value))

    normalized = parsed._replace(
        scheme=(parsed.scheme or "https").lower(),
        netloc=parsed.netloc.lower(),
        query=urlencode(clean_query, doseq=True),
        fragment="",
    )
    return urlunparse(normalized)


def discover_topic_urls(topic_name: str, max_articles: int = 50) -> List[Dict[str, Any]]:
    """
    Discover candidate article URLs for a topic and return deduped records.
    """
    if not settings.SERPAPI_API_KEY:
        return []

    params = {
        "engine": "google_news",
        "q": topic_name,
        "num": max_articles,
        "api_key": settings.SERPAPI_API_KEY,
    }

    search = GoogleSearch(params)
    results = search.get_dict()
    api_articles = results.get("news_results", [])

    deduped: Dict[str, Dict[str, Any]] = {}
    for article in api_articles:
        candidate = article.get("highlight", article)
        raw_url = candidate.get("link")
        title = candidate.get("title")
        if not raw_url or not title:
            continue

        canonical_url = normalize_url(raw_url)
        if canonical_url in deduped:
            continue

        source_info = candidate.get("source", {})
        if "name" not in source_info:
            source_info = article.get("source", {})

        deduped[canonical_url] = {
            "url": raw_url,
            "canonical_url": canonical_url,
            "title": title,
            "description": candidate.get("snippet", "No description available."),
            "source": source_info.get("name", "Unknown"),
            "image_url": candidate.get("thumbnail") or candidate.get("thumbnail_small") or article.get("thumbnail"),
            "date": candidate.get("date", "now"),
        }

        if len(deduped) >= max_articles:
            break

    return list(deduped.values())
