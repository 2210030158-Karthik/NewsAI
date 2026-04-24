from __future__ import annotations

from datetime import datetime
import json
from typing import Any, Dict, Optional

import dateparser
from bs4 import BeautifulSoup

MIN_CONTENT_CHARS = 250
BLOCKED_PAGE_MARKERS = (
    "enable js and disable any ad blocker",
    "access denied",
    "verify you are human",
    "captcha",
    "bot detection",
)


def _parse_possible_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    parsed = dateparser.parse(value)
    return parsed


def _clean_text(text: str) -> str:
    return " ".join(text.split())


def _looks_like_blocked_page(raw_html: str) -> bool:
    html_lower = raw_html.lower()
    return any(marker in html_lower for marker in BLOCKED_PAGE_MARKERS)


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


def _extract_with_json_ld(raw_html: str) -> Dict[str, Any]:
    soup = BeautifulSoup(raw_html, "html.parser")

    scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
    for script in scripts:
        payload = script.string or script.get_text(strip=True)
        if not payload:
            continue

        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            continue

        nodes = parsed if isinstance(parsed, list) else [parsed]
        for node in nodes:
            if not isinstance(node, dict):
                continue

            node_type = node.get("@type")
            node_type_list = node_type if isinstance(node_type, list) else [node_type]
            node_type_text = " ".join(str(item).lower() for item in node_type_list if item)
            if "article" not in node_type_text and "news" not in node_type_text:
                continue

            body_text = node.get("articleBody") or node.get("text")
            clean_text = _clean_text(str(body_text)) if body_text else None

            author_raw = node.get("author")
            author_value = None
            if isinstance(author_raw, dict):
                author_value = author_raw.get("name")
            elif isinstance(author_raw, list):
                names = []
                for author in author_raw:
                    if isinstance(author, dict) and author.get("name"):
                        names.append(str(author.get("name")))
                    elif isinstance(author, str):
                        names.append(author)
                author_value = ", ".join(names) if names else None
            elif isinstance(author_raw, str):
                author_value = author_raw

            image_raw = node.get("image")
            image_url = None
            if isinstance(image_raw, str):
                image_url = image_raw
            elif isinstance(image_raw, list) and image_raw:
                image_url = str(image_raw[0])
            elif isinstance(image_raw, dict):
                image_url = image_raw.get("url")

            return {
                "clean_text": clean_text,
                "title": node.get("headline") or node.get("name"),
                "author": author_value,
                "image_url": image_url,
                "published_at": _parse_possible_date(node.get("datePublished")),
                "canonical_url": node.get("url"),
                "status": "extracted_jsonld" if clean_text else "jsonld_empty",
            }

    return {
        "clean_text": None,
        "title": None,
        "author": None,
        "image_url": None,
        "published_at": None,
        "canonical_url": None,
        "status": "jsonld_empty",
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

    if _looks_like_blocked_page(raw_html):
        return {
            "clean_text": None,
            "word_count": None,
            "title": None,
            "author": None,
            "published_at": None,
            "image_url": None,
            "canonical_url": url,
            "status": "blocked_source",
        }

    trafilatura_result = _extract_with_trafilatura(raw_html, url)
    best = trafilatura_result
    bs4_result = None
    jsonld_result = None

    if not best.get("clean_text") or len(best["clean_text"]) < MIN_CONTENT_CHARS:
        bs4_result = _extract_with_bs4(raw_html)
        jsonld_result = _extract_with_json_ld(raw_html)

        for candidate in (bs4_result, jsonld_result):
            if candidate.get("clean_text") and len(candidate["clean_text"]) > len(best.get("clean_text") or ""):
                best = candidate

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
