from celery import Celery
from celery.signals import worker_ready, worker_shutdown
from config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND, METRICS_ENABLED

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
    task_default_queue='default',
    task_routes={
        'tasks.send_push_notification': {'queue': 'default', 'routing_key': 'push'},
        'tasks.send_email_notification': {'queue': 'default', 'routing_key': 'email'},
    },
    worker_send_task_events=True,
    task_send_sent_event=True,
)

if METRICS_ENABLED:
    @worker_ready.connect
    def capture_worker_ready(**kwargs):
        worker = kwargs.get('sender')
        if worker:
            app.current_worker = worker

    @worker_shutdown.connect
    def capture_worker_shutdown(**kwargs):
        if hasattr(app, 'current_worker'):
            delattr(app, 'current_worker')
