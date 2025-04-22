import time
import threading
import logging
from collections import defaultdict
from typing import Dict, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class MetricsCollector:
    def __init__(self):
        self._metrics_data = defaultdict(
            lambda: defaultdict(
                lambda: defaultdict(
                    lambda: {}
                )
            )
        )
        self._lock = threading.RLock()
        logger.info("Metrics collector initialized")
    
    def record_notification(
        self, 
        server_id: str, 
        channel: str, 
        status: str
    ) -> None:
        with self._lock:
            current_time = int(time.time())
            
            if current_time not in self._metrics_data[server_id][channel][status]:
                self._metrics_data[server_id][channel][status][current_time] = 0
            
            self._metrics_data[server_id][channel][status][current_time] += 1
            
            logger.debug(f"Recorded metric: server={server_id}, channel={channel}, status={status}")
    
    def get_metrics(
        self, 
        server_id: Optional[str] = None, 
        channel: Optional[str] = None,
        time_period: Optional[int] = None
    ) -> Dict[str, Any]:
        with self._lock:
            result = {
                "timestamp": datetime.now().isoformat(),
                "servers": {}
            }
            
            current_time = int(time.time())
            min_time = current_time - time_period if time_period else 0
            
            servers = [server_id] if server_id else self._metrics_data.keys()
            
            for srv in servers:
                if srv not in self._metrics_data:
                    continue
                
                server_data = {"channels": {}}
                
                channels = [channel] if channel else self._metrics_data[srv].keys()
                
                for chnl in channels:
                    if chnl not in self._metrics_data[srv]:
                        continue
                    
                    channel_data = {
                        "total": 0,
                        "statuses": {}
                    }
                    
                    for status, timestamps in self._metrics_data[srv][chnl].items():
                        status_count = 0
                        
                        for ts, count in timestamps.items():
                            if ts >= min_time:
                                status_count += count
                        
                        if status_count > 0:
                            channel_data["statuses"][status] = status_count
                            channel_data["total"] += status_count
                    
                    if channel_data["total"] > 0:
                        server_data["channels"][chnl] = channel_data
                
                total_notifications = sum(
                    channel_data["total"] 
                    for channel_data in server_data["channels"].values()
                )
                
                if total_notifications > 0:
                    server_data["total"] = total_notifications
                    result["servers"][srv] = server_data
            
            result["total"] = sum(
                server_data["total"] 
                for server_data in result["servers"].values()
            )
            
            return result

metrics = MetricsCollector()
