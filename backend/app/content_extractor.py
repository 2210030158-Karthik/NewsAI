from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

import dateparser
from bs4 import BeautifulSoup

MIN_CONTENT_CHARS = 250


def _parse_possible_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    parsed = dateparser.parse(value)
    return parsed


def _clean_text(text: str) -> str:
    return " ".join(text.split())


def _extract_metadata_from_meta_tags(soup: BeautifulSoup) -> Dict[str, Optional[str]]:
    def _meta_content(key: str, attr_name: str = "property") -> Optional[str]:
        tag = soup.find("meta", attrs={attr_name: key})
        if not tag:
            return None
        content = tag.get("content")
        return content.strip() if isinstance(content, str) and content.strip() else None

    title = _meta_content("og:title") or _meta_content("twitter:title", "name")
    image_url = _meta_content("og:image") or _meta_content("twitter:image", "name")
    author = _meta_content("author", "name")
    published_raw = (
        _meta_content("article:published_time")
        or _meta_content("og:published_time")
        or _meta_content("date", "name")
    )
    canonical_url = None
    canonical_link = soup.find("link", rel="canonical")
    if canonical_link and canonical_link.get("href"):
        canonical_url = canonical_link.get("href")

    return {
        "title": title,
        "image_url": image_url,
        "author": author,
        "published_raw": published_raw,
        "canonical_url": canonical_url,
    }


def _extract_with_trafilatura(raw_html: str, url: Optional[str]) -> Dict[str, Any]:
    try:
        import trafilatura
    except ImportError:
        return {"clean_text": None, "status": "extractor_missing"}

    extracted = trafilatura.extract(
        raw_html,
        url=url,
        include_comments=False,
        include_tables=False,
        favor_precision=True,
    )
    metadata = trafilatura.extract_metadata(raw_html, default_url=url)

    if not extracted:
        return {"clean_text": None, "status": "trafilatura_empty"}

    return {
        "clean_text": _clean_text(extracted),
        "title": getattr(metadata, "title", None),
        "author": getattr(metadata, "author", None),
        "published_at": _parse_possible_date(getattr(metadata, "date", None)),
        "image_url": getattr(metadata, "image", None),
        "canonical_url": getattr(metadata, "url", None),
        "status": "extracted_trafilatura",
    }


def _extract_with_bs4(raw_html: str) -> Dict[str, Any]:
    soup = BeautifulSoup(raw_html, "html.parser")

    for tag in soup(["script", "style", "noscript", "svg", "form", "aside", "nav", "footer"]):
        tag.decompose()

    metadata = _extract_metadata_from_meta_tags(soup)

    article_node = soup.find("article")
    if article_node:
        paragraph_text = "\n".join(
            p.get_text(" ", strip=True)
            for p in article_node.find_all("p")
            if p.get_text(" ", strip=True)
        )
    else:
        paragraph_text = "\n".join(
            p.get_text(" ", strip=True)
            for p in soup.find_all("p")
            if len(p.get_text(" ", strip=True)) >= 40
        )

    clean_text = _clean_text(paragraph_text)
    if not clean_text:
        return {
            "clean_text": None,
            "title": metadata.get("title"),
            "author": metadata.get("author"),
            "image_url": metadata.get("image_url"),
            "published_at": _parse_possible_date(metadata.get("published_raw")),
            "canonical_url": metadata.get("canonical_url"),
            "status": "bs4_empty",
        }

    return {
        "clean_text": clean_text,
        "title": metadata.get("title"),
        "author": metadata.get("author"),
        "image_url": metadata.get("image_url"),
        "published_at": _parse_possible_date(metadata.get("published_raw")),
        "canonical_url": metadata.get("canonical_url"),
        "status": "extracted_bs4",
    }


def extract_article_content(raw_html: Optional[str], url: Optional[str] = None) -> Dict[str, Any]:
    """
    Extract full article content and metadata using fallback strategy.
    """
    if not raw_html:
        return {
            "clean_text": None,
            "word_count": None,
            "title": None,
            "author": None,
            "published_at": None,
            "image_url": None,
            "canonical_url": None,
            "status": "no_html",
        }

    trafilatura_result = _extract_with_trafilatura(raw_html, url)
    best = trafilatura_result

    if not best.get("clean_text") or len(best["clean_text"]) < MIN_CONTENT_CHARS:
        bs4_result = _extract_with_bs4(raw_html)
        if bs4_result.get("clean_text") and len(bs4_result["clean_text"]) > len(best.get("clean_text") or ""):
            best = bs4_result

    clean_text = best.get("clean_text")
    word_count = len(clean_text.split()) if clean_text else None

    return {
        "clean_text": clean_text,
        "word_count": word_count,
        "title": best.get("title"),
        "author": best.get("author"),
        "published_at": best.get("published_at"),
        "image_url": best.get("image_url"),
        "canonical_url": best.get("canonical_url"),
        "status": best.get("status") if clean_text else "extraction_failed",
    }
