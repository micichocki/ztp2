import sys
import socket
import threading
import uvicorn
from fastapi import FastAPI, HTTPException, Query
from typing import Optional

from celery_app import app
from service import NotificationService


def create_metrics_app(worker_type, port):
    metrics_app = FastAPI(
        title=f"{worker_type.capitalize()} Worker Metrics",
        description=f"Metrics API for {worker_type} worker",
        version="1.0.0"
    )
    
    @metrics_app.get("/metrics")
    def get_metrics(
        server: Optional[str] = None,
        channel: Optional[str] = None,
        period: Optional[int] = Query(None, ge=1)
    ):
        try:
            metrics_data = NotificationService.get_metrics(
                server_id=server,
                channel=channel,
                time_period=period
            )
            return metrics_data
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    def run_server():
        uvicorn.run(metrics_app, host="0.0.0.0", port=port, log_level="error")
    
    thread = threading.Thread(target=run_server, daemon=True)
    return thread


def start_push_worker():
    worker = app.Worker(
        hostname=f'push.worker.{socket.gethostname()}',
        queues=['default'],
        concurrency=1,
        loglevel='INFO',
        consumer_arguments={
            'routing_key': 'push'
        }
    )

    from config import PUSH_METRICS_PORT
    metrics_thread = create_metrics_app('push', PUSH_METRICS_PORT)
    metrics_thread.start()
    
    worker.start()


def start_email_worker():
    worker = app.Worker(
        hostname=f'email.worker.{socket.gethostname()}',
        queues=['default'],
        concurrency=1,
        loglevel='INFO',
        consumer_arguments={
            'routing_key': 'email'
        }
    )

    from config import EMAIL_METRICS_PORT
    metrics_thread = create_metrics_app('email', EMAIL_METRICS_PORT)
    metrics_thread.start()
    
    worker.start()


if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] not in ('push', 'email'):
        print("Usage: python workers.py [push|email]")
        sys.exit(1)

    if sys.argv[1] == 'push':
        start_push_worker()
    elif sys.argv[1] == 'email':
        start_email_worker()
