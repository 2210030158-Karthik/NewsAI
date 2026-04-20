from datetime import datetime, timezone

from .celery_app import celery_app


@celery_app.task(name="app.tasks.healthcheck")
def healthcheck_task() -> dict:
    return {
        "status": "ok",
        "service": "personalized_news_worker",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
