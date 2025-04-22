import click
import socket
import threading
import uvicorn
from fastapi import FastAPI, HTTPException, Query
from typing import Optional

from celery_app import app
from service import NotificationService
from models import DeliveryChannel


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

class Worker:

    @staticmethod
    def start_worker(channels=None):
        if channels is None:
            channels = [ch.value for ch in DeliveryChannel]
        
        if isinstance(channels, str):
            channels = [channels]
        
        worker_name = f'worker.{socket.gethostname()}'
        
        print(f"Starting worker {worker_name} for channels: {', '.join(channels)}")
        
        binding_keys = channels
        
        worker = app.Worker(
            hostname=worker_name,
            queues=['notifications'],
            concurrency=1,
            loglevel='INFO',
            consumer_arguments={
                'x-binding-key': binding_keys
            }
        )

        from config import WORKER_METRICS_PORT
        metrics_thread = create_metrics_app('worker', WORKER_METRICS_PORT)
        metrics_thread.start()

        worker.start()


@click.command()
@click.argument('channels', nargs=-1, type=click.Choice(['push', 'email', 'all']))
def main(channels):
    if not channels or 'all' in channels:
        Worker.start_worker()
    else:
        Worker.start_worker(channels)

if __name__ == '__main__':
    main()
