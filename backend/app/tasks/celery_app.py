from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "labreportai",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.analyze", "app.tasks.cleanup"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# Celery Beat schedule — periodic tasks
celery_app.conf.beat_schedule = {
    "cleanup-expired-reports": {
        "task": "cleanup_expired_reports",
        "schedule": 3600.0,  # every hour
    },
}
