from datetime import datetime
from typing import Optional
from fastapi import HTTPException, Query, Depends

from exception import NotificationNotFoundException, InvalidNotificationStateException
from models import NotificationRequest
from service import NotificationService
import logging

logger = logging.getLogger(__name__)


class HealthController:
    @staticmethod
    async def health_check():
        return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

class NotificationController:
    @staticmethod
    async def create_push_notification(request: NotificationRequest):
        try:
            notification_id = NotificationService.schedule_push_notification(request)
            
            return {
                'notification_id': notification_id,
                'status': 'scheduled',
                'message': 'Push notification scheduled'
            }
        except Exception as e:
            logger.error(f"Error scheduling push notification: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @staticmethod
    async def create_email_notification(request: NotificationRequest):
        try:
            notification_id = NotificationService.schedule_email_notification(request)
            
            return {
                'notification_id': notification_id,
                'status': 'scheduled',
                'message': 'Email notification scheduled'
            }
        except Exception as e:
            logger.error(f"Error scheduling email notification: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @staticmethod
    async def force_notification_delivery(notification_id: str):
        try:
            result = NotificationService.force_delivery(notification_id)
            return result
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
            return result
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
    async def get_notification(notification_id: str):
        try:
            result = NotificationService.get_notification_status(notification_id)
            return result
        except NotificationNotFoundException as e:
            logger.warning(f"Notification not found: {notification_id}")
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            logger.error(f"Error retrieving notification: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @staticmethod
    async def list_notifications(
        status: Optional[str] = None,
        timezone: Optional[str] = None,
        recipient_id: Optional[str] = None,
        limit: int = Query(100, ge=1, le=1000),
        offset: int = Query(0, ge=0)
    ):
        try:
            notifications = NotificationService.list_notifications(
                status=status,
                timezone=timezone,
                recipient_id=recipient_id,
                limit=limit,
                offset=offset
            )
            
            return {
                'count': len(notifications),
                'notifications': notifications
            }
        except Exception as e:
            logger.error(f"Error listing notifications: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

class MetricsController:
    @staticmethod
    async def get_metrics(
        server: Optional[str] = None,
        channel: Optional[str] = None,
        period: Optional[int] = None
    ):
        try:
            metrics = NotificationService.get_metrics(
                server_id=server,
                channel=channel,
                time_period=period
            )
            return metrics
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Error retrieving metrics: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
