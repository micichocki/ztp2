import click
import socket
import threading
import uvicorn
from fastapi import FastAPI, HTTPException
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
        channel: Optional[str] = None
    ):
        try:
            metrics_data = NotificationService.get_metrics(
                server_id=server,
                channel=channel
            )
            return metrics_data
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    def run_server():
        uvicorn.run(metrics_app, host="0.0.0.0", port=port, log_level="error")

    thread = threading.Thread(target=run_server, daemon=True)
    return thread

class Worker:

    @staticmethod
    def start_worker():
        worker_name = f'worker.{socket.gethostname()}'
        
        print(f"Starting worker {worker_name}")
        worker = app.Worker(
            hostname=worker_name,
            queues=['notifications'],
            concurrency=1,
            loglevel='INFO',
            prefetch_multiplier=1,
            max_priority=100,
            max_tasks_per_child=100,
            task_time_limit=1800,
            task_soft_time_limit=1500
        )

        from config import WORKER_METRICS_PORT
        metrics_thread = create_metrics_app('worker', WORKER_METRICS_PORT)
        metrics_thread.start()

        worker.start()

@click.command()
def main():
    Worker.start_worker()

if __name__ == '__main__':
    main()

