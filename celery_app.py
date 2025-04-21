from celery import Celery
from celery.signals import worker_ready, worker_shutdown, task_success, task_failure
from config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND, METRICS_ENABLED
import sys

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

@task_success.connect
def print_notification_success(sender=None, result=None, **kwargs):
    task = sender.name
    
    if task in ['tasks.send_push_notification', 'tasks.send_email_notification']:
        task_id = kwargs.get('task_id', 'unknown')
        args = kwargs.get('args', [])
        notification_id = args[0] if args else 'unknown'
        
        channel_type = 'PUSH' if 'push' in task else 'EMAIL'
        print(f"\n✅ SUCCESS: {channel_type} notification {notification_id} delivered successfully\n", 
              file=sys.stdout, flush=True)

@task_failure.connect
def print_notification_failure(sender=None, exception=None, **kwargs):
    task = sender.name
    
    if task in ['tasks.send_push_notification', 'tasks.send_email_notification']:
        task_id = kwargs.get('task_id', 'unknown')
        args = kwargs.get('args', [])
        notification_id = args[0] if args else 'unknown'
        
        channel_type = 'PUSH' if 'push' in task else 'EMAIL'
        print(f"\n❌ FAILED: {channel_type} notification {notification_id} delivery failed: {str(exception)}\n", 
              file=sys.stderr, flush=True)
