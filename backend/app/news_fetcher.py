from datetime import datetime
from typing import Any, Dict, List

import dateparser
from serpapi import GoogleSearch

from .config import settings
from .discovery import discover_topic_urls


def parse_date(date_string: str) -> datetime:
    """
    Parses date strings like "11/20/2024" or "2 hours ago".
    """
    parsed = dateparser.parse(date_string)
    if parsed:
        return parsed
    return datetime.now()


def fetch_articles_for_topic(topic_name: str, max_articles: int = 20) -> List[Dict[str, Any]]:
    """
    Fetches discovered and deduped article metadata for one topic.
    """
    if not settings.SERPAPI_API_KEY:
        print("Error: SERPAPI_API_KEY is not set. Cannot fetch articles.")
        return []

    print(f"Fetching articles for topic: {topic_name}...")
    try:
        discovered_articles = discover_topic_urls(topic_name=topic_name, max_articles=max_articles)
        cleaned_articles: List[Dict[str, Any]] = []

        for article in discovered_articles:
            title = article.get("title")
            url = article.get("url")
            if not title or not url:
                continue

            published_dt = parse_date(article.get("date", "now"))
            cleaned_articles.append(
                {
                    "title": title,
                    "description": article.get("description", "No description available."),
                    "url": url,
                    "canonical_url": article.get("canonical_url"),
                    "source": article.get("source", "Unknown"),
                    "image_url": article.get("image_url"),
                    "published_at": published_dt,
                }
            )

        print(f"Successfully fetched {len(cleaned_articles)} articles for {topic_name}.")
        return cleaned_articles
    except Exception as exc:
        print(f"Error fetching or parsing SerpApi data: {exc}")
        return []


def fetch_top_stories(max_articles: int = 10) -> List[Dict[str, Any]]:
    """
    Fetches Google News top stories (no explicit query term).
    """
    if not settings.SERPAPI_API_KEY:
        print("Error: SERPAPI_API_KEY is not set. Cannot fetch top stories.")
        return []

    print("Fetching LIVE Top Stories (no query)...")
    params = {
        "engine": "google_news",
        "num": max_articles,
        "api_key": settings.SERPAPI_API_KEY,
    }

    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        api_articles = results.get("news_results", [])
        if len(api_articles) > max_articles:
            api_articles = api_articles[:max_articles]

        cleaned_articles: List[Dict[str, Any]] = []
        for article in api_articles:
            story = article.get("highlight", article)
            title = story.get("title")
            url = story.get("link")
            if not title or not url:
                continue

            source_info = story.get("source", {})
            if "name" not in source_info:
                source_info = article.get("source", {})

            cleaned_articles.append(
                {
                    "title": title,
                    "description": story.get("snippet", "No description available."),
                    "url": url,
                    "source": source_info.get("name", "Unknown"),
                    "image_url": story.get("thumbnail") or article.get("thumbnail"),
                    "published_at": parse_date(story.get("date", "now")),
                }
            )

        print(f"Successfully fetched {len(cleaned_articles)} top stories.")
        return cleaned_articles
    except Exception as exc:
        print(f"Error fetching or parsing SerpApi data for Top Stories: {exc}")
        return []


if __name__ == "__main__":
    print("Fetching test articles for 'Technology'...")
    test_articles = fetch_articles_for_topic("Technology", 3)
    if not test_articles:
        print("Failed to fetch test articles.")
    for idx, article in enumerate(test_articles, start=1):
        print(f"\n--- Article {idx} ---")
        print(f"Title: {article['title']}")
        print(f"Source: {article['source']}")
        print(f"Date: {article['published_at']}")

