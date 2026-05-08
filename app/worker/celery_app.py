from celery import Celery
from app.settings import settings

celery_app = Celery(
    "agentic_uat",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.worker.tasks"],
)
celery_app.conf.task_track_started = True
celery_app.conf.result_expires = 3600 * 24
