from __future__ import annotations

from datetime import datetime
import hashlib
import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import classifier, content_extractor, models, news_fetcher, scraper
from .config import settings


logger = logging.getLogger(__name__)


def _normalize_domain(url: str) -> str:
    parsed = urlparse(url)
    domain = (parsed.netloc or "").lower().strip()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def _safe_status(value: Optional[str], max_length: int = 50) -> str:
    if not value:
        return "unknown"
    return value[:max_length]


def _has_full_content(article: models.Article) -> bool:
    clean_text = (article.clean_text or "").strip()
    if not clean_text:
        return False
    return len(clean_text) >= settings.FULL_ARTICLE_MIN_CHARS


def create_ingestion_run(
    db_session: Session,
    topic_ids: List[int],
    status: str = "queued",
) -> models.IngestionRun:
    run = models.IngestionRun(
        run_id=uuid4().hex,
        status=status,
        topics_total=len(set(topic_ids)),
        started_at=datetime.utcnow(),
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)
    return run


def mark_ingestion_run_failed(db_session: Session, run_id: str, message: str) -> None:
    run = (
        db_session.query(models.IngestionRun)
        .filter(models.IngestionRun.run_id == run_id)
        .one_or_none()
    )
    if run:
        run.status = "failed"
        run.ended_at = datetime.utcnow()
        db_session.add(run)
        db_session.commit()

    _record_error(
        db_session=db_session,
        run_id=run_id,
        topic_id=None,
        url=None,
        stage="pipeline",
        error=message,
    )


def _record_error(
    db_session: Session,
    run_id: Optional[str],
    topic_id: Optional[int],
    url: Optional[str],
    stage: str,
    error: Any,
) -> None:
    if not run_id:
        return

    err = models.IngestionError(
        run_id=run_id,
        topic_id=topic_id,
        url=(url or "")[:1000] or None,
        stage=stage[:50],
        error_type=type(error).__name__[:100],
        message=str(error)[:5000],
    )
    db_session.add(err)
    db_session.commit()


def _load_topic_inputs(db_session: Session, topic_ids: List[int]) -> tuple[List[models.Topic], Dict[str, int], List[str]]:
    requested_topics = (
        db_session.query(models.Topic)
        .filter(models.Topic.id.in_(topic_ids))
        .all()
    )
    all_topics = db_session.query(models.Topic).all()
    topic_name_to_id = {topic.name: topic.id for topic in all_topics}
    topic_names = list(topic_name_to_id.keys())
    return requested_topics, topic_name_to_id, topic_names


def _persist_run_progress(
    db_session: Session,
    run: models.IngestionRun,
    summary: Dict[str, Any],
) -> None:
    run.urls_discovered = summary["urls_discovered"]
    run.urls_scraped = summary["urls_scraped"]
    run.success_count = summary["success_count"]
    run.fail_count = summary["fail_count"]
    run.status = "running"
    db_session.add(run)
    db_session.commit()


def _upsert_source_for_url(db_session: Session, article_url: str) -> Optional[models.Source]:
    source_domain = _normalize_domain(article_url)
    if not source_domain:
        return None

    source_row = (
        db_session.query(models.Source)
        .filter(models.Source.domain == source_domain)
        .one_or_none()
    )
    if source_row:
        return source_row

    source_row = models.Source(domain=source_domain)
    db_session.add(source_row)
    db_session.flush()
    return source_row


def _enrich_existing_article(db_session: Session, article: models.Article, article_data: Dict[str, Any]) -> Dict[str, bool]:
    if _has_full_content(article):
        return {"success": True, "scraped": False, "created": False}

    scraped_payload = scraper.fetch_article_html(article_data["url"])
    extracted = content_extractor.extract_article_content(
        raw_html=scraped_payload.get("raw_html"),
        url=scraped_payload.get("final_url") or article_data["url"],
    )

    clean_text = extracted.get("clean_text")
    extraction_status = extracted.get("status") or "extraction_failed"
    if scraped_payload.get("error") and not scraped_payload.get("raw_html"):
        extraction_status = "fetch_failed"

    article.canonical_url = (
        article.canonical_url
        or article_data.get("canonical_url")
        or extracted.get("canonical_url")
        or scraped_payload.get("final_url")
    )
    article.raw_html = scraped_payload.get("raw_html") or article.raw_html
    article.clean_text = clean_text or article.clean_text
    article.word_count = extracted.get("word_count") or article.word_count
    article.author = extracted.get("author") or article.author
    article.image_url = article.image_url or article_data.get("image_url") or extracted.get("image_url")
    article.extraction_status = _safe_status(extraction_status)
    article.fetched_at = scraped_payload.get("fetched_at") or datetime.utcnow()

    if clean_text and not article.content_hash:
        article.content_hash = hashlib.sha256(clean_text.encode("utf-8")).hexdigest()

    db_session.add(article)
    db_session.commit()
    return {"success": True, "scraped": True, "created": False}


def hydrate_article_content(db_session: Session, article: models.Article) -> models.Article:
    """
    Ensure an existing article has full readable content stored.
    """
    _enrich_existing_article(
        db_session=db_session,
        article=article,
        article_data={
            "url": article.url,
            "image_url": article.image_url,
            "canonical_url": article.canonical_url,
        },
    )
    db_session.refresh(article)
    return article


def _create_new_article(
    db_session: Session,
    article_data: Dict[str, Any],
    topic_name_to_id: Dict[str, int],
    all_topic_names: List[str],
) -> Dict[str, bool]:
    scraped_payload = scraper.fetch_article_html(article_data["url"])
    extracted = content_extractor.extract_article_content(
        raw_html=scraped_payload.get("raw_html"),
        url=scraped_payload.get("final_url") or article_data["url"],
    )

    extraction_status = extracted.get("status") or "extraction_failed"
    if scraped_payload.get("error") and not scraped_payload.get("raw_html"):
        extraction_status = "fetch_failed"
    extraction_status = _safe_status(extraction_status)

    clean_text = extracted.get("clean_text")
    content_to_classify = (
        clean_text[:3500]
        if clean_text
        else f"{article_data['title']}. {article_data.get('description') or ''}"
    )

    classification_list = classifier.classify_article_content(
        content=content_to_classify,
        topics=all_topic_names,
    )
    classification_results = {
        item.get("topic"): item.get("score")
        for item in classification_list
        if item.get("topic") in topic_name_to_id
    }

    source_row = _upsert_source_for_url(db_session, article_data["url"])

    published_at = (
        extracted.get("published_at")
        or article_data.get("published_at")
        or datetime.utcnow()
    )

    canonical_url = (
        article_data.get("canonical_url")
        or extracted.get("canonical_url")
        or scraped_payload.get("final_url")
        or article_data["url"]
    )

    content_hash = (
        hashlib.sha256(clean_text.encode("utf-8")).hexdigest()
        if clean_text
        else None
    )

    article = models.Article(
        title=article_data["title"],
        description=article_data.get("description"),
        url=article_data["url"],
        canonical_url=canonical_url,
        source=article_data.get("source"),
        source_id=source_row.id if source_row else None,
        author=extracted.get("author"),
        image_url=article_data.get("image_url") or extracted.get("image_url"),
        raw_html=scraped_payload.get("raw_html"),
        clean_text=clean_text,
        word_count=extracted.get("word_count"),
        content_hash=content_hash,
        published_at=published_at,
        fetched_at=scraped_payload.get("fetched_at") or datetime.utcnow(),
        extraction_status=extraction_status,
    )
    db_session.add(article)
    db_session.flush()

    for topic_name, score in classification_results.items():
        if score is None or score <= 0.1:
            continue

        db_session.add(
            models.ArticleTopicScore(
                article_id=article.id,
                topic_id=topic_name_to_id[topic_name],
                score=score,
            )
        )

    db_session.commit()
    return {"success": True, "scraped": True, "created": True}


def process_ingestion_topic_batch(
    db_session: Session,
    topic_ids: List[int],
    run_id: Optional[str] = None,
    max_articles_per_topic: int = 10,
) -> Dict[str, Any]:
    unique_topic_ids = list(dict.fromkeys(topic_ids))
    topics_to_fetch, topic_name_to_id, all_topic_names = _load_topic_inputs(db_session, unique_topic_ids)

    if not topics_to_fetch:
        raise ValueError("No matching topics found for ingestion.")
    if not all_topic_names:
        raise ValueError("No topics found in database for classifier.")

    run = None
    if run_id:
        run = (
            db_session.query(models.IngestionRun)
            .filter(models.IngestionRun.run_id == run_id)
            .one_or_none()
        )
        if run is None:
            run = models.IngestionRun(
                run_id=run_id,
                status="running",
                topics_total=len(topics_to_fetch),
                started_at=datetime.utcnow(),
            )
            db_session.add(run)
        run.status = "running"
        run.topics_total = len(topics_to_fetch)
        db_session.commit()

    summary: Dict[str, Any] = {
        "run_id": run_id,
        "topics_total": len(topics_to_fetch),
        "urls_discovered": 0,
        "urls_scraped": 0,
        "success_count": 0,
        "fail_count": 0,
        "new_articles": 0,
    }
    progress_update_every = max(1, settings.INGESTION_PROGRESS_UPDATE_EVERY)
    processed_article_urls = 0

    logger.info(
        "Ingestion run started: run_id=%s, topics_total=%s, max_articles_per_topic=%s",
        run_id,
        len(topics_to_fetch),
        max_articles_per_topic,
    )

    for topic in topics_to_fetch:
        logger.info("Ingestion topic start: run_id=%s, topic_id=%s, topic_name=%s", run_id, topic.id, topic.name)
        fetched_articles_data = news_fetcher.fetch_articles_for_topic(
            topic_name=topic.name,
            max_articles=max_articles_per_topic,
        )
        logger.info(
            "Ingestion topic discovery complete: run_id=%s, topic_id=%s, discovered=%s",
            run_id,
            topic.id,
            len(fetched_articles_data),
        )
        summary["urls_discovered"] += len(fetched_articles_data)

        for article_data in fetched_articles_data:
            article_url = article_data.get("url")
            if not article_url:
                continue

            processed_article_urls += 1

            try:
                existing_article = (
                    db_session.query(models.Article)
                    .filter(models.Article.url == article_url)
                    .one_or_none()
                )

                if existing_article:
                    result = _enrich_existing_article(db_session, existing_article, article_data)
                else:
                    result = _create_new_article(
                        db_session,
                        article_data,
                        topic_name_to_id=topic_name_to_id,
                        all_topic_names=all_topic_names,
                    )

                if result["scraped"]:
                    summary["urls_scraped"] += 1
                if result["created"]:
                    summary["new_articles"] += 1
                if result["success"]:
                    summary["success_count"] += 1

            except IntegrityError:
                db_session.rollback()
                # Another process likely inserted this URL in parallel.
                summary["success_count"] += 1
            except Exception as exc:
                db_session.rollback()
                summary["fail_count"] += 1
                logger.warning(
                    "Article processing failed: run_id=%s, topic_id=%s, url=%s, error=%s",
                    run_id,
                    topic.id,
                    article_url,
                    exc,
                )
                _record_error(
                    db_session=db_session,
                    run_id=run_id,
                    topic_id=topic.id,
                    url=article_url,
                    stage="article_processing",
                    error=exc,
                )

            if run and processed_article_urls % progress_update_every == 0:
                _persist_run_progress(
                    db_session=db_session,
                    run=run,
                    summary=summary,
                )
                logger.info(
                    "Ingestion run checkpoint persisted: run_id=%s, processed_article_urls=%s, urls_discovered=%s, urls_scraped=%s, success_count=%s, fail_count=%s",
                    run_id,
                    processed_article_urls,
                    summary["urls_discovered"],
                    summary["urls_scraped"],
                    summary["success_count"],
                    summary["fail_count"],
                )

    if run:
        run.urls_discovered = summary["urls_discovered"]
        run.urls_scraped = summary["urls_scraped"]
        run.success_count = summary["success_count"]
        run.fail_count = summary["fail_count"]
        run.status = "completed" if summary["fail_count"] == 0 else "completed_with_errors"
        run.ended_at = datetime.utcnow()
        db_session.add(run)
        db_session.commit()

    logger.info(
        "Ingestion run finished: run_id=%s, status=%s, urls_discovered=%s, urls_scraped=%s, success_count=%s, fail_count=%s, new_articles=%s",
        run_id,
        run.status if run else "completed",
        summary["urls_discovered"],
        summary["urls_scraped"],
        summary["success_count"],
        summary["fail_count"],
        summary["new_articles"],
    )

    return summary
