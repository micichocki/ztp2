import logging
from typing import Dict, Optional, Any
from datetime import datetime, timezone
from collections import defaultdict
import requests

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
            "timestamp": datetime.now(timezone.utc).isoformat(),
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

            worker_task_stats = self._get_worker_task_stats(server_id, start_date, end_date)
            worker_ids = self._collect_worker_ids(server_id, active_workers, worker_task_stats)

            for worker_id in worker_ids:
                server_data = self._create_server_data_object(
                    worker_id, active_workers, reserved_tasks, active_tasks, worker_task_stats
                )
                result["servers"][worker_id] = server_data

        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")

        return result

    def _collect_worker_ids(
        self, 
        server_id: Optional[str],
        active_workers: Dict[str, Any],
        worker_task_stats: Dict[str, Dict[str, int]]
    ) -> list:
        worker_ids = []

        if server_id:
            worker_ids.append(server_id)
        else:
            worker_ids.extend(active_workers.keys())
            
            for worker_id in worker_task_stats.keys():
                if worker_id not in worker_ids:
                    worker_ids.append(worker_id)
                    
            for recorded_server in self._stats_records.keys():
                if recorded_server not in worker_ids:
                    worker_ids.append(recorded_server)
                    
        return worker_ids

    def _create_server_data_object(
        self,
        worker_id: str,
        active_workers: Dict[str, Any],
        reserved_tasks: Dict[str, Any],
        active_tasks: Dict[str, Any],
        worker_task_stats: Dict[str, Dict[str, int]]
    ) -> Dict[str, Any]:
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

        if worker_id in worker_task_stats:
            server_data.update(worker_task_stats[worker_id])

        return server_data

    def _get_worker_task_stats(
        self, 
        worker_filter: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Dict[str, int]]:
        try:
            task_data = self._get_tasks_from_api()
            worker_stats = self._process_tasks_by_worker(
                task_data, 
                worker_filter=worker_filter,
                start_date=start_date,
                end_date=end_date
            )
            
            return worker_stats
            
        except Exception as e:
            logger.error(f"Error fetching worker task stats: {e}")
            return {}
            
    def _get_tasks_from_api(self) -> Dict[str, Dict[str, Any]]:
        try:
            response = requests.get("http://127.0.0.1:5555/api/tasks")
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            logger.error(f"Error making API request to Flower: {e}")
            return {}
    
    def _process_tasks_by_worker(
        self, 
        tasks: Dict[str, Dict[str, Any]], 
        worker_filter: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Dict[str, int]]:
        worker_stats = defaultdict(lambda: {
            "success_tasks": 0,
            "failed_tasks": 0,
            "pending_tasks": 0
        })
        
        for task_id, task_data in tasks.items():
            worker_id = task_data.get('worker')
            if not worker_id:
                continue
                
            if worker_filter and worker_filter != worker_id:
                continue
                
            if not self._is_in_date_range(task_data, start_date, end_date):
                continue
            
            self._count_task_by_state(worker_stats, worker_id, task_data)
        
        return dict(worker_stats)
        
    def _is_in_date_range(
        self,
        task_data: Dict[str, Any],
        start_date: Optional[datetime],
        end_date: Optional[datetime]
    ) -> bool:
        task_timestamp = task_data.get('timestamp')
        if not task_timestamp:
            return True
            
        task_datetime = datetime.fromtimestamp(task_timestamp)
        
        if start_date and task_datetime < start_date:
            return False
            
        if end_date and task_datetime > end_date:
            return False
            
        return True
        
    def _count_task_by_state(
        self,
        worker_stats: Dict[str, Dict[str, int]],
        worker_id: str,
        task_data: Dict[str, Any]
    ) -> None:
        state = task_data.get('state', '').upper()
        
        if state == 'SUCCESS':
            worker_stats[worker_id]['success_tasks'] += 1
        elif state == 'FAILURE':
            worker_stats[worker_id]['failed_tasks'] += 1
        elif state == 'RECEIVED':
            worker_stats[worker_id]['pending_tasks'] += 1
