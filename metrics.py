import logging
from typing import Dict, Optional, Any, List
from datetime import datetime
from collections import defaultdict

from celery_app import app

logger = logging.getLogger(__name__)


class MetricsCollector:
    def __init__(self):
        self._stats_records = defaultdict(list)
        logger.info("Metrics collector initialized")

    def get_metrics(
            self,
            server_id: Optional[str] = None,
            channel: Optional[str] = None,
            start_date: Optional[datetime] = None,
            end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        result = {
            "timestamp": datetime.now().isoformat(),
            "servers": {},
            "total": 0
        }

        if start_date:
            result["start_date"] = start_date.isoformat()
        if end_date:
            result["end_date"] = end_date.isoformat()

        try:
            inspector = app.control.inspect()

            active_workers = inspector.stats() or {}
            active_queues = inspector.active_queues() or {}
            reserved_tasks = inspector.reserved() or {}
            active_tasks = inspector.active() or {}

            worker_ids = []

            if server_id:
                worker_ids.append(server_id)
            else:
                worker_ids.extend(active_workers.keys())
                for recorded_server in self._stats_records.keys():
                    if recorded_server not in worker_ids:
                        worker_ids.append(recorded_server)

            for worker_id in worker_ids:
                server_data = {
                    "channels": {},
                    "total": 0,
                    "worker_info": {}
                }

                if worker_id in active_workers:
                    server_data["worker_info"]["stats"] = active_workers[worker_id]

                if worker_id in active_queues:
                    server_data["worker_info"]["queues"] = active_queues[worker_id]

                if worker_id in reserved_tasks:
                    server_data["worker_info"]["reserved_tasks"] = len(reserved_tasks[worker_id])

                if worker_id in active_tasks:
                    server_data["worker_info"]["active_tasks"] = len(active_tasks[worker_id])

                if worker_id in self._stats_records:
                    for record in self._stats_records[worker_id]:
                        record_time = record["timestamp"]
                        record_channel = record["channel"]
                        record_status = record["status"]

                        if start_date and record_time < start_date:
                            continue
                        if end_date and record_time > end_date:
                            continue

                        if channel and channel != record_channel:
                            continue

                        if record_channel not in server_data["channels"]:
                            server_data["channels"][record_channel] = {
                                "total": 0,
                                "statuses": {}
                            }

                        if record_status not in server_data["channels"][record_channel]["statuses"]:
                            server_data["channels"][record_channel]["statuses"][record_status] = 0

                        server_data["channels"][record_channel]["statuses"][record_status] += 1
                        server_data["channels"][record_channel]["total"] += 1
                        server_data["total"] += 1

                if server_data["channels"] or server_data["worker_info"]:
                    result["servers"][worker_id] = server_data
                    result["total"] += server_data.get("total", 0)

        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")

        return result

metrics = MetricsCollector()