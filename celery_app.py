from celery import Celery
from celery.signals import worker_ready, worker_shutdown
from config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND, METRICS_ENABLED
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
        'tasks.send_push_notification': {'queue': 'notifications', 'routing_key': 'push'},
        'tasks.send_email_notification': {'queue': 'notifications', 'routing_key': 'email'},
    },
    worker_send_task_events=True,
    task_send_sent_event=True,
    task_track_started=True,
    worker_log_color=True,
)

if METRICS_ENABLED:
    @worker_ready.connect
    def capture_worker_ready(**kwargs):
        worker = kwargs.get('sender')
        if worker:
            app.current_worker = worker
            logger.info(f"Worker {worker.hostname} is ready")

    @worker_shutdown.connect
    def capture_worker_shutdown(**kwargs):
        if hasattr(app, 'current_worker'):
            logger.info(f"Worker {app.current_worker.hostname} is shutting down")
            delattr(app, 'current_worker')
