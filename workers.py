import click
import socket
from celery_app import app


class Worker:

    @staticmethod
    def start_worker():
        hostname = socket.gethostname()
        worker_name = f'worker@{hostname}'
        
        app.conf.worker_proc_alive_timeout = 60
        app.conf.worker_name = worker_name
        
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


        worker.start()

@click.command()
def main():
    Worker.start_worker()

if __name__ == '__main__':
    main()

