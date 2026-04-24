from datetime import datetime
from typing import Any, Dict, Optional

import requests

from .config import settings

DEFAULT_TIMEOUT_SECONDS = settings.SCRAPER_TIMEOUT_SECONDS
MAX_HTML_CHARS = 2_000_000

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch_article_html(url: str, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> Dict[str, Any]:
    """
    Fetch raw HTML for an article URL with predictable metadata for downstream extraction.
    """
    base_payload: Dict[str, Any] = {
        "url": url,
        "final_url": None,
        "status_code": None,
        "raw_html": None,
        "content_type": None,
        "fetched_at": datetime.utcnow(),
        "error": None,
    }

    try:
        response = requests.get(
            url,
            headers=_DEFAULT_HEADERS,
            timeout=timeout_seconds,
            allow_redirects=True,
        )
        content_type = (response.headers.get("Content-Type") or "").lower()
        html = response.text if "html" in content_type or "xml" in content_type else ""
        if html and len(html) > MAX_HTML_CHARS:
            html = html[:MAX_HTML_CHARS]

        base_payload.update(
            {
                "final_url": response.url,
                "status_code": response.status_code,
                "raw_html": html or None,
                "content_type": content_type,
            }
        )

        if response.status_code >= 400:
            base_payload["error"] = f"HTTP {response.status_code}"
        if not base_payload["raw_html"]:
            base_payload["error"] = base_payload["error"] or "No HTML content"

        return base_payload
    except requests.RequestException as exc:
        base_payload["error"] = str(exc)
        return base_payload
