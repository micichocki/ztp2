from typing import Optional
from fastapi import HTTPException

from exception import NotificationNotFoundException, InvalidNotificationStateException, ValidationError
from models import NotificationRequest, NotificationResponse, NotificationListResponse, ScheduleResponse, \
    ActionResponse, Notification
from service import NotificationService
import logging

logger = logging.getLogger(__name__)

class NotificationController:
    @staticmethod
    async def create_push_notification(request: NotificationRequest):
        try:
            task_id = NotificationService.schedule_push_notification(request)
            
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
    
    @staticmethod
    async def create_email_notification(request: NotificationRequest):
        try:
            task_id = NotificationService.schedule_email_notification(request)
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
    
    @staticmethod
    async def force_notification_delivery(notification_id: str):
        try:
            result = NotificationService.force_delivery(notification_id)
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
    
    @staticmethod
    async def cancel_notification(notification_id: str):
        try:
            result = NotificationService.cancel_notification(notification_id)
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
    
    @staticmethod
    async def get_notification(notification_id: str) -> Notification:
        try:
            return NotificationService.get_notification(notification_id)
        except NotificationNotFoundException as e:
            logger.warning(f"Notification not found: {notification_id}")
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            logger.error(f"Error retrieving notification: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @staticmethod
    async def list_notifications() -> NotificationListResponse:
        try:
            notifications = NotificationService.list_notifications()
            notification_responses = [NotificationResponse(**notification) for notification in notifications]

            return NotificationListResponse(
                count=len(notification_responses),
                notifications=notification_responses
            )
        except Exception as e:
            logger.error(f"Error listing notifications: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

class MetricsController:
    @staticmethod
    async def get_metrics(
        server: Optional[str] = None,
        channel: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ):
        try:
            metrics = NotificationService.get_metrics(
                server_id=server,
                channel=channel,
                start_date=start_date,
                end_date=end_date
            )
            return metrics
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Error retrieving metrics: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

