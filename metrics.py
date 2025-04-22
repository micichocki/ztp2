import logging
from typing import Dict, Optional, Any
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
            start_date: Optional[datetime] = None,
            end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        result = {
            "timestamp": datetime.now().isoformat(),
            "servers": {},
        }

        if start_date:
            result["start_date"] = start_date.isoformat()
        if end_date:
            result["end_date"] = end_date.isoformat()

        try:
            inspector = app.control.inspect()

            active_workers = inspector.stats() or {}
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
                    "total_tasks": 0,
                    "pending_tasks": 0,
                    "active_tasks": 0
                }

                if worker_id in active_workers:
                    server_data["total_tasks"] = active_workers[worker_id].get("total", 0)

                if worker_id in reserved_tasks:
                    server_data["pending_tasks"] = len(reserved_tasks[worker_id])

                if worker_id in active_tasks:
                    server_data["active_tasks"] = len(active_tasks[worker_id])

                if worker_id in self._stats_records and (start_date or end_date):
                    filtered_records = self._stats_records[worker_id]
                    
                    if start_date or end_date:
                        filtered_records = [
                            record for record in filtered_records
                            if (not start_date or record["timestamp"] >= start_date) and
                               (not end_date or record["timestamp"] <= end_date)
                        ]
                    

                result["servers"][worker_id] = server_data

        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")

        return result
