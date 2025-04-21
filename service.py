import random
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import pytz
import logging

from config import APPROPRIATE_HOURS_START, APPROPRIATE_HOURS_END
from exception import NotificationNotFoundException, InvalidNotificationStateException
from models import DeliveryChannel, Notification, NotificationStatus, db_session, NotificationRequest
from notification_validator import NotificationValidator
from tasks import schedule_notification, force_immediate_delivery, cancel_notification
from sqlalchemy import and_
from metrics import metrics

logger = logging.getLogger(__name__)

class NotificationService:

    @staticmethod
    def schedule_push_notification(
        notification: NotificationRequest,
    ) -> str:
        validator = NotificationValidator(notification)
        validator.validate()
        task = schedule_notification.delay(
            recipient_id=notification.recipient_id,
            content=notification.content,
            channel=DeliveryChannel.PUSH,
            timezone=notification.timezone,
            scheduled_time=notification.scheduled_time
        )
        return task.id

    @staticmethod
    def schedule_email_notification(
     notification: NotificationRequest,
    ) -> str:
        validator = NotificationValidator(notification)
        validator.validate()
        task = schedule_notification.delay(
            recipient_id=notification.recipient_id,
            content=notification.content,
            channel=DeliveryChannel.EMAIL,
            timezone=notification.timezone,
            scheduled_time=notification.scheduled_time
        )
        return task.id
    
    @staticmethod
    def force_delivery(notification_id: str) -> Dict[str, Any]|None:
        session = db_session()
        try:
            notification = session.query(Notification).filter(Notification.id == notification_id).first()
            if not notification:
                logger.warning(f"Force delivery attempt for non-existent notification: {notification_id}")
                raise NotificationNotFoundException(f"Notification not found: {notification_id}")
            
            if notification.status != NotificationStatus.SCHEDULED:
                logger.warning(
                    f"Cannot force delivery for notification {notification_id} with status {notification.status}"
                )
                raise InvalidNotificationStateException(
                    f"Cannot force delivery for notification with status {notification.status}"
                )

            logger.info(f"Forcing immediate delivery of notification {notification_id}")
            result = force_immediate_delivery.delay(notification_id)
            
            return {
                "status": "success",
                "message": "Notification delivery forced",
                "notification_id": notification_id,
                "task_id": result.id
            }
        finally:
            session.close()
    
    @staticmethod
    def cancel_notification(notification_id: str) -> Dict[str, Any]|None:
        """Cancel a scheduled notification"""
        session = db_session()
        try:
            notification = session.query(Notification).filter(Notification.id == notification_id).first()
            if not notification:
                logger.warning(f"Cancel attempt for non-existent notification: {notification_id}")
                raise NotificationNotFoundException(f"Notification not found: {notification_id}")
            
            if notification.status != NotificationStatus.SCHEDULED:
                logger.warning(
                    f"Cannot cancel notification {notification_id} with status {notification.status}"
                )
                raise InvalidNotificationStateException(
                    f"Cannot cancel notification with status {notification.status}"
                )
            
            logger.info(f"Cancelling scheduled notification {notification_id}")
            result = cancel_notification.delay(notification_id)
            
            return {
                "status": "success",
                "message": "Notification cancelled",
                "notification_id": notification_id,
                "task_id": result.id
            }
        finally:
            session.close()
        
    @staticmethod
    def get_notification_status(notification_id: str) -> Dict[str, Any]|None:
        session = db_session()
        try:
            notification = session.query(Notification).filter(Notification.id == notification_id).first()
            if not notification:
                logger.warning(f"Status request for non-existent notification: {notification_id}")
                raise NotificationNotFoundException(f"Notification not found: {notification_id}")
            
            status_map = {
                "scheduled": "Pending",
                "processing": "Pending",
                "delivered": "Sent",
                "failed": "Failed",
                "cancelled": "Cancelled"
            }
            
            local_tz = pytz.timezone(notification.timezone)
            scheduled_local = notification.scheduled_time.astimezone(local_tz)
            
            hour = scheduled_local.hour
            is_appropriate = APPROPRIATE_HOURS_START <= hour < APPROPRIATE_HOURS_END
            
            estimated_delivery_time = scheduled_local.isoformat()
            if not is_appropriate and notification.status != NotificationStatus.CANCELLED:
                next_day = scheduled_local.date()
                if hour >= APPROPRIATE_HOURS_END:
                    next_day = next_day + timedelta(days=1)
                    
                adjusted_time = local_tz.localize(
                    datetime.combine(next_day, datetime.min.time().replace(
                        hour=APPROPRIATE_HOURS_START, minute=0, second=0
                    ))
                )
                estimated_delivery_time = adjusted_time.isoformat()
            
            return {
                "id": notification.id,
                "recipient_id": notification.recipient_id,
                "content": notification.content,
                "channel": notification.channel,
                "status": status_map.get(notification.status, "Unknown"),
                "created_at": notification.created_at.isoformat(),
                "scheduled_time": notification.scheduled_time.isoformat(),
                "timezone": notification.timezone,
                "local_scheduled_time": scheduled_local.isoformat(),
                "appropriate_delivery": is_appropriate,
                "estimated_delivery_time": estimated_delivery_time,
                "attempt_count": notification.attempt_count
            }
        finally:
            session.close()
    
    @staticmethod
    def list_notifications(
        status: Optional[str] = None,
        timezone: Optional[str] = None,
        recipient_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]|None:
        session = db_session()
        try:
            query = session.query(Notification)
            
            filters = []
            if status:
                status_map = {
                    "Pending": [NotificationStatus.SCHEDULED, NotificationStatus.PROCESSING],
                    "Sent": [NotificationStatus.DELIVERED],
                    "Failed": [NotificationStatus.FAILED],
                    "Cancelled": [NotificationStatus.CANCELLED]
                }
                internal_statuses = status_map.get(status, [])
                if internal_statuses:
                    filters.append(Notification.status.in_(internal_statuses))
            
            if timezone:
                filters.append(Notification.timezone == timezone)
                
            if recipient_id:
                filters.append(Notification.recipient_id == recipient_id)
            
            if filters:
                query = query.filter(and_(*filters))
            
            query = query.order_by(Notification.created_at.desc())
            query = query.limit(limit).offset(offset)
            
            notifications = query.all()
            
            status_map = {
                NotificationStatus.SCHEDULED: "Pending",
                NotificationStatus.PROCESSING: "Pending",
                NotificationStatus.DELIVERED: "Sent",
                NotificationStatus.FAILED: "Failed",
                NotificationStatus.CANCELLED: "Cancelled"
            }
            
            results = []
            for notif in notifications:
                local_tz = pytz.timezone(notif.timezone)
                scheduled_local = notif.scheduled_time.astimezone(local_tz)

                hour = scheduled_local.hour
                is_appropriate = APPROPRIATE_HOURS_START <= hour < APPROPRIATE_HOURS_END
                
                results.append({
                    "id": notif.id,
                    "recipient_id": notif.recipient_id,
                    "content": notif.content,
                    "channel": notif.channel,
                    "status": status_map.get(notif.status, "Unknown"),
                    "created_at": notif.created_at.isoformat(),
                    "scheduled_time": notif.scheduled_time.isoformat(),
                    "timezone": notif.timezone,
                    "local_scheduled_time": scheduled_local.isoformat(),
                    "appropriate_delivery": is_appropriate,
                    "attempt_count": notif.attempt_count
                })
            
            return results
        finally:
            session.close()
            
    @staticmethod
    def get_metrics(
        server_id: Optional[str] = None,
        channel: Optional[str] = None,
        time_period: Optional[int] = None
    ) -> Dict[str, Any]:
        if time_period is not None and time_period <= 0:
            raise ValueError("Time period must be a positive integer")
        return metrics.get_metrics(server_id, channel, time_period)
