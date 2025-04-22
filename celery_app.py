from celery import Celery
from celery.signals import worker_ready, worker_shutdown
from config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND, METRICS_ENABLED
from kombu import Exchange, Queue
import logging

logger = logging.getLogger(__name__)

app = Celery(
    'notification_system',
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=['tasks']
)

app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_queue='notifications',
    task_routes={
        'tasks.send_push_notification': {'queue': 'notifications'},
        'tasks.send_email_notification': {'queue': 'notifications'},
    },
    worker_send_task_events=True,
    task_send_sent_event=True,
    task_track_started=True,
    task_inherit_parent_priority=True,
    worker_log_color=True,
)
