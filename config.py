import os

MAX_RETRY_ATTEMPTS = 3
RETRY_DELAY = 1

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://ztp2:ztp2@localhost:5432/ztp2')
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'amqp://ztp2:ztp2@localhost:5672//')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'db+postgresql://ztp2:ztp2@localhost:5432/ztp2')

APPROPRIATE_HOURS_START = 8
APPROPRIATE_HOURS_END = 23

METRICS_ENABLED = True
PUSH_METRICS_PORT = 5001
EMAIL_METRICS_PORT = 5002
WORKER_METRICS_PORT = 5003

FLOWER_PORT = int(os.environ.get('FLOWER_PORT', 5555))
FLOWER_HOST = os.environ.get('FLOWER_HOST', '0.0.0.0')
FLOWER_UNAUTHENTICATED_API=''
