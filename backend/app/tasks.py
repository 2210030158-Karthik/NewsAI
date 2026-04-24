from datetime import datetime, timezone
import logging

from .celery_app import celery_app
from .config import settings
from .db import SessionLocal
from . import ingestion_service, models


logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.healthcheck")
def healthcheck_task() -> dict:
    return {
        "status": "ok",
        "service": "personalized_news_worker",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@celery_app.task(name="app.tasks.process_ingestion_run")
def process_ingestion_run(run_id: str, topic_ids: list[int], max_articles_per_topic: int = 10) -> dict:
    db_session = SessionLocal()
    try:
        logger.info(
            "Task process_ingestion_run started: run_id=%s, topics=%s, max_articles_per_topic=%s",
            run_id,
            len(topic_ids),
            max_articles_per_topic,
        )
        summary = ingestion_service.process_ingestion_topic_batch(
            db_session=db_session,
            topic_ids=topic_ids,
            run_id=run_id,
            max_articles_per_topic=max_articles_per_topic,
        )
        logger.info("Task process_ingestion_run completed: run_id=%s, summary=%s", run_id, summary)
        return summary
    except Exception as exc:
        logger.exception("Task process_ingestion_run failed: run_id=%s, error=%s", run_id, exc)
        ingestion_service.mark_ingestion_run_failed(db_session, run_id=run_id, message=str(exc))
        raise
    finally:
        db_session.close()


@celery_app.task(name="app.tasks.enqueue_scheduled_ingestion")
def enqueue_scheduled_ingestion() -> dict:
    db_session = SessionLocal()
    try:
        topics = (
            db_session.query(models.Topic)
            .filter(models.Topic.active.is_(True))
            .order_by(models.Topic.id.asc())
            .limit(settings.ASYNC_INGESTION_TOPIC_BATCH_SIZE)
            .all()
        )
        topic_ids = [topic.id for topic in topics]

        if not topic_ids:
            return {"status": "skipped", "reason": "No active topics found."}

        run = ingestion_service.create_ingestion_run(
            db_session=db_session,
            topic_ids=topic_ids,
            status="queued",
        )
    finally:
        db_session.close()

    async_result = process_ingestion_run.delay(
        run.run_id,
        topic_ids,
        settings.INGESTION_MAX_ARTICLES_PER_TOPIC,
    )
    return {
        "status": "queued",
        "run_id": run.run_id,
        "task_id": async_result.id,
        "topics_total": len(topic_ids),
    }
