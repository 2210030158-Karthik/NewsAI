from celery import Celery
from celery.schedules import crontab

from .config import settings

celery_app = Celery(
    "personalized_news_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
)

if settings.ENABLE_ASYNC_INGESTION:
    celery_app.conf.beat_schedule = {
        "scheduled-topic-ingestion": {
            "task": "app.tasks.enqueue_scheduled_ingestion",
            "schedule": crontab(minute=0, hour="*/5"),
        }
    }

# Discover tasks in app.tasks and future task modules.
celery_app.autodiscover_tasks(["app"])
