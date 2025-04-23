from typing import Optional, List
from fastapi import HTTPException

from exceptions.exception import NotificationNotFoundException, InvalidNotificationStateException, ValidationError
from models import NotificationRequest, ScheduleResponse, \
    ActionResponse, Notification
from service import NotificationService
from repositories.notification_repository import NotificationRepository
import logging

logger = logging.getLogger(__name__)

class NotificationController:
    def __init__(self, service: NotificationService = None):
        self.service = service
    
    async def create_push_notification(self, request: NotificationRequest):
        try:
            task_id = self.service.schedule_push_notification(request)
            
            return ScheduleResponse(
                task_id=task_id,
                status='scheduled',
                message='Push notification scheduled'
            )
        except ValidationError as e:
            logger.warning(f"Validation error: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Error scheduling push notification: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def create_email_notification(self, request: NotificationRequest):
        try:
            task_id = self.service.schedule_email_notification(request)
            return ScheduleResponse(
                task_id=task_id,
                status='scheduled',
                message='Email notification scheduled'
            )
        except ValidationError as e:
            logger.warning(f"Validation error: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Error scheduling email notification: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def force_notification_delivery(self, notification_id: str):
        try:
            result = self.service.force_delivery(notification_id)
            return ActionResponse(**result)
        except NotificationNotFoundException as e:
            logger.warning(f"Notification not found: {notification_id}")
            raise HTTPException(status_code=404, detail=str(e))
        except InvalidNotificationStateException as e:
            logger.warning(f"Invalid notification state: {notification_id}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Error forcing notification delivery: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def cancel_notification(self, notification_id: str):
        try:
            result = self.service.cancel_notification(notification_id)
            return ActionResponse(**result)
        except NotificationNotFoundException as e:
            logger.warning(f"Notification not found: {notification_id}")
            raise HTTPException(status_code=404, detail=str(e))
        except InvalidNotificationStateException as e:
            logger.warning(f"Invalid notification state: {notification_id}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Error canceling notification: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def get_notification(self, notification_id: str) -> Notification:
        try:
            return self.service.get_notification(notification_id)
        except NotificationNotFoundException as e:
            logger.warning(f"Notification not found: {notification_id}")
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            logger.error(f"Error retrieving notification: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def list_notifications(self) -> List[Notification]:
        try:
            return self.service.list_notifications()
        except Exception as e:
            logger.error(f"Error listing notifications: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

class MetricsController:
    def __init__(self, service: NotificationService = None):
        self.service = service or NotificationService(NotificationRepository())
    
    async def get_metrics(
        self,
        server: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ):
        try:
            metrics = self.service.get_metrics(
                server_id=server,
                start_date=start_date,
                end_date=end_date
            )
            return metrics
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Error retrieving metrics: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
