import random
from typing import Optional, List, Dict, Any
import logging
from datetime import datetime

from exceptions.exception import NotificationNotFoundException, InvalidNotificationStateException
from models import DeliveryChannel, Notification, NotificationStatus, db_session, NotificationRequest
from validators.notification_validator import NotificationValidator
from tasks import schedule_notification, force_immediate_delivery, cancel_notification
from metrics import metrics

logger = logging.getLogger(__name__)

class NotificationService:

    @staticmethod
    def _calculate_probabilistic_priority(base_priority: int = 5) -> int:
        rand_value = random.randint(0, 100)
        probability_factor = base_priority / 10.0
        actual_priority = int(rand_value * probability_factor + (base_priority * 10 * (1 - probability_factor)))
        logger.info(f"Base priority {base_priority} converted to actual priority {actual_priority}")
        return actual_priority

    @staticmethod
    def _schedule_notification(
        notification: NotificationRequest,
        channel: DeliveryChannel
    ) -> str:
        validator = NotificationValidator(notification)
        validator.validate()

        actual_priority = NotificationService._calculate_probabilistic_priority(notification.priority)

        task = schedule_notification.apply_async(
            args=[
                notification.recipient_id,
                notification.content,
                channel,
                notification.timezone,
                notification.scheduled_time
            ],
            priority=actual_priority,
        )
        return task.id

    @staticmethod
    def schedule_push_notification(
        notification: NotificationRequest,
    ) -> str:
        return NotificationService._schedule_notification(notification, DeliveryChannel.PUSH)

    @staticmethod
    def schedule_email_notification(
     notification: NotificationRequest,
    ) -> str:
        return NotificationService._schedule_notification(notification, DeliveryChannel.EMAIL)

    @staticmethod
    def _get_notification_or_raise(notification_id: str, expected_status: Optional[NotificationStatus] = None) -> Notification|None:
        session = db_session()
        try:
            notification = session.query(Notification).filter(Notification.id == notification_id).first()
            if not notification:
                logger.warning(f"Request for non-existent notification: {notification_id}")
                raise NotificationNotFoundException(f"Notification not found: {notification_id}")

            if expected_status and notification.status != expected_status:
                logger.warning(
                    f"Invalid status for notification {notification_id}: expected {expected_status}, got {notification.status}"
                )
                raise InvalidNotificationStateException(
                    f"Cannot perform operation on notification with status {notification.status}"
                )

            return notification
        finally:
            session.close()

    @staticmethod
    def force_delivery(notification_id: str) -> Dict[str, Any]|None:
        notification = NotificationService._get_notification_or_raise(
            notification_id,
            expected_status=NotificationStatus.SCHEDULED
        )

        logger.info(f"Forcing immediate delivery of notification {notification.id}")
        result = force_immediate_delivery.delay(notification.id)

        return {
            "status": "success",
            "message": "Notification delivery forced",
            "notification_id": notification_id,
            "task_id": result.id
        }

    @staticmethod
    def cancel_notification(notification_id: str) -> Dict[str, Any]|None:
        notification = NotificationService._get_notification_or_raise(
            notification_id,
            expected_status=NotificationStatus.SCHEDULED
        )

        logger.info(f"Cancelling scheduled notification {notification.id}")
        result = cancel_notification.delay(notification.id)

        return {
            "status": "success",
            "message": "Notification cancelled",
            "notification_id": notification_id,
            "task_id": result.id
        }

    @staticmethod
    def get_notification(notification_id: str) -> Notification|None:
        return NotificationService._get_notification_or_raise(notification_id)

    @staticmethod
    def list_notifications() -> List[Notification]|None:
        session = db_session()
        try:
            query = session.query(Notification)
            query = query.order_by(Notification.created_at.desc())
            notifications = query.all()
            return notifications
        finally:
            session.close()

    @staticmethod
    def get_metrics(
        server_id: Optional[str] = None,
        channel: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        start_datetime = None
        end_datetime = None
        
        if start_date:
            try:
                start_datetime = datetime.fromisoformat(start_date)
            except ValueError:
                logger.warning(f"Invalid start_date format: {start_date}, expected ISO format")
        
        if end_date:
            try:
                end_datetime = datetime.fromisoformat(end_date)
            except ValueError:
                logger.warning(f"Invalid end_date format: {end_date}, expected ISO format")
        
        return metrics.get_metrics(
            server_id=server_id, 
            channel=channel,
            start_date=start_datetime,
            end_date=end_datetime
        )
