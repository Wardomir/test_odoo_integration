from celery import Celery
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "odoo_integration",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={},
    beat_max_loop_interval=10,  # Check for new tasks every 10 seconds
)
