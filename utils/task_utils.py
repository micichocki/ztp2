import logging

from celery_app import app
from models import DeliveryChannel

logger = logging.getLogger(__name__)


class TaskManager:

    @staticmethod
    def revoke_task(task_id: str) -> bool:
        if not task_id:
            logger.warning("No task ID provided for revocation")
            return False
        
        try:
            app.control.revoke(
                task_id, 
                terminate=True, 
                signal='SIGTERM', 
                destination=None
            )
            
            logger.info(f"Revoked task {task_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to revoke task {task_id}: {str(e)}")
            return False

    @staticmethod
    def get_channel_task(channel: DeliveryChannel):
        from tasks import send_push_notification, send_email_notification
        
        channel_tasks = {
            DeliveryChannel.PUSH: send_push_notification,
            DeliveryChannel.EMAIL: send_email_notification,
        }
        
        if channel not in channel_tasks:
            logger.error(f"Unsupported channel: {channel}")
            raise ValueError(f"Unsupported channel: {channel}")
            
        return channel_tasks[channel]
