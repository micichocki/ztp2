import random
from typing import Optional, List, Dict, Any
import logging
from datetime import datetime

from exceptions.exception import NotificationNotFoundException, InvalidNotificationStateException
from models import DeliveryChannel, Notification, NotificationStatus, NotificationRequest
from validators.notification_validator import NotificationValidator
from tasks import schedule_notification, force_immediate_delivery, cancel_notification
from metrics import MetricsCollector
from repositories.notification_repository import NotificationRepository

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self, repository: NotificationRepository = None):
        self.repository = repository or NotificationRepository()

    def _calculate_probabilistic_priority(self, base_priority: int = 5) -> int:
        rand_value = random.randint(0, 100)
        probability_factor = base_priority / 10.0
        actual_priority = int(rand_value * probability_factor + (base_priority * 10 * (1 - probability_factor)))
        logger.info(f"Base priority {base_priority} converted to actual priority {actual_priority}")
        return actual_priority

    def _schedule_notification(
        self,
        notification: NotificationRequest,
        channel: DeliveryChannel
    ) -> str:
        validator = NotificationValidator(notification)
        validator.validate()

        actual_priority = self._calculate_probabilistic_priority(notification.priority)

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

    def schedule_push_notification(
        self,
        notification: NotificationRequest,
    ) -> str:
        return self._schedule_notification(notification, DeliveryChannel.PUSH)

    def schedule_email_notification(
        self,
        notification: NotificationRequest,
    ) -> str:
        return self._schedule_notification(notification, DeliveryChannel.EMAIL)

    def _get_notification_or_raise(self, notification_id: str, expected_status: Optional[NotificationStatus] = None) -> Notification:
        notification = self.repository.get_by_id(notification_id)
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

    def force_delivery(self, notification_id: str) -> Dict[str, Any]:
        notification = self._get_notification_or_raise(
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

    def cancel_notification(self, notification_id: str) -> Dict[str, Any]:
        notification = self._get_notification_or_raise(
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

    def get_notification(self, notification_id: str) -> Notification:
        return self._get_notification_or_raise(notification_id)

    def list_notifications(self) -> List[Notification]:
        return self.repository.get_all()

    def get_metrics(
        self,
        server_id: Optional[str] = None,
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
        metrics = MetricsCollector()
        return metrics.get_metrics(
            server_id=server_id, 
            start_date=start_datetime,
            end_date=end_datetime
        )
