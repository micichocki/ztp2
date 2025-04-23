import logging
import pytz
from datetime import datetime
from celery.exceptions import MaxRetriesExceededError
from typing import Optional, Union, Any

from celery_app import app
from models import Notification, NotificationStatus, DeliveryChannel, db_session
from repositories.notification_repository import NotificationRepository
from config import MAX_RETRY_ATTEMPTS, RETRY_DELAY
from utils.time_utils import TimeUtils
from utils.task_utils import TaskManager
from utils.delivery_utils import NotificationDeliveryService

logger = logging.getLogger(__name__)


def _handle_notification_delivery(
    task_instance: Any,
    notification_id: str,
    channel: DeliveryChannel
) -> Optional[bool]:
    session = db_session()
    repository = NotificationRepository(session)
    try:
        notification = repository.get_by_id(notification_id)
        if not notification:
            logger.error(f"Notification {notification_id} not found")
            return False

        if notification.status == NotificationStatus.CANCELLED:
            logger.info(f"Notification {notification_id} has been cancelled, skipping delivery")
            return False

        notification.status = NotificationStatus.PROCESSING
        repository.commit(notification)

        try:
            delivery_method = NotificationDeliveryService.get_delivery_method(channel)
            
            result = NotificationDeliveryService.process_delivery_attempt(
                notification=notification,
                channel=channel,
                delivery_method=delivery_method,
                task_instance=task_instance,
                max_retry_attempts=MAX_RETRY_ATTEMPTS,
                retry_delay=RETRY_DELAY
            )
            
            if result is True:
                notification.status = NotificationStatus.DELIVERED
                repository.commit()
                return True
            
            notification.status = NotificationStatus.FAILED
            repository.commit()
            return False
            
        except MaxRetriesExceededError:
            notification.status = NotificationStatus.FAILED
            repository.commit()
            return False
        except Exception as e:
            notification.status = NotificationStatus.FAILED
            repository.commit()
            logger.error(f"Unhandled exception in delivery: {str(e)}")
            return False
            
    finally:
        session.close()


@app.task(bind=True, max_retries=MAX_RETRY_ATTEMPTS)
def send_push_notification(self, notification_id: str) -> Optional[bool]:
    return _handle_notification_delivery(self, notification_id, DeliveryChannel.PUSH)


@app.task(bind=True, max_retries=MAX_RETRY_ATTEMPTS)
def send_email_notification(self, notification_id: str) -> Optional[bool]:
    return _handle_notification_delivery(self, notification_id, DeliveryChannel.EMAIL)


@app.task
def schedule_notification(
        recipient_id: str,
        content: str,
        channel: DeliveryChannel,
        timezone: str = "UTC",
        scheduled_time: Optional[str] = None
) -> Optional[Union[str, bool]]:
    notification = Notification(
        recipient_id=recipient_id,
        content=content,
        channel=channel,
        timezone=timezone,
        scheduled_time=scheduled_time
    )
    
    notification_id = notification.id
    
    session = db_session()
    repository = NotificationRepository(session)
    try:
        repository.save(notification)
        
        logger.info(f"Created notification {notification_id} for delivery via {channel}")
        
        scheduled_dt = TimeUtils.parse_scheduled_time(scheduled_time, timezone)
        if not scheduled_dt:
            scheduled_dt = datetime.now(pytz.UTC)
            logger.info(f"No scheduled time provided, using current time: {scheduled_dt.isoformat()}")
        else:
            logger.info(f"Processing notification with explicit scheduled time: {scheduled_dt.isoformat()}")
        
        if not TimeUtils.is_within_appropriate_hours(scheduled_dt, timezone):
            logger.info(f"Scheduled time {scheduled_dt.isoformat()} is outside appropriate hours in timezone {timezone}")
            
            scheduled_dt = TimeUtils.get_next_appropriate_time(scheduled_dt, timezone)
            
            notification.scheduled_time = scheduled_dt
            repository.commit()
            
            logger.info(f"Notification {notification_id} rescheduled for {scheduled_dt.isoformat()}")

        try:
            channel_task = TaskManager.get_channel_task(channel)
        except ValueError as e:
            logger.error(str(e))
            return False

        task = channel_task.apply_async(
            args=[notification_id],
            eta=scheduled_dt,
            queue='notifications',
        )
        
        notification.task_id = task.id
        repository.commit()
        logger.info(f"Stored task ID {task.id} for notification {notification_id}")

        logger.info(f"Scheduled notification {notification_id} with task {task.id} for delivery at {scheduled_dt.isoformat()}")
        return task.id
    except Exception as e:
        session.rollback()
        logger.error(f"Error scheduling notification: {str(e)}")
        raise
    finally:
        session.close()


@app.task
def force_immediate_delivery(notification_id: str) -> Optional[bool]:
    session = db_session()
    repository = NotificationRepository(session)
    try:
        notification = repository.get_by_id(notification_id)
        if not notification:
            logger.error(f"Notification {notification_id} not found")
            return False

        if notification.status != NotificationStatus.SCHEDULED:
            logger.warning(f"Cannot force delivery for notification {notification_id} with status {notification.status}")
            return False

        original_task_id = notification.task_id
        if original_task_id:
            logger.info(f"Revoking existing task {original_task_id} for notification {notification_id}")
            if not TaskManager.revoke_task(original_task_id):
                logger.warning(f"Failed to revoke task {original_task_id}, proceeding with immediate delivery anyway")
        else:
            logger.warning(f"No task ID found for notification {notification_id}")
        
        notification.status = NotificationStatus.PROCESSING
        repository.commit()

        logger.info(f"Forcing immediate delivery of notification {notification_id}")

        try:
            channel_task = TaskManager.get_channel_task(notification.channel)
        except ValueError as e:
            logger.error(str(e))
            return False

        task = channel_task.apply_async(
            args=[notification_id], 
            countdown=0,
            queue='notifications',
        )
        
        notification.task_id = task.id
        repository.commit()
        logger.info(f"Updated notification {notification_id} with new task ID {task.id}")
        
        return True
    except Exception as e:
        session.rollback()
        logger.error(f"Error forcing immediate delivery: {str(e)}")
        raise
    finally:
        session.close()


@app.task
def cancel_notification(notification_id: str) -> Optional[bool]:
    session = db_session()
    repository = NotificationRepository(session)
    try:
        notification = repository.get_by_id(notification_id)
        if not notification:
            logger.error(f"Notification {notification_id} not found")
            return False
        
        if notification.status != NotificationStatus.SCHEDULED:
            logger.warning(f"Cannot cancel notification {notification_id} with status {notification.status}")
            return False
        
        original_task_id = notification.task_id
        if original_task_id:
            logger.info(f"Revoking task {original_task_id} for cancelled notification {notification_id}")
            if not TaskManager.revoke_task(original_task_id):
                logger.warning(f"Failed to revoke task {original_task_id} directly")
        else:
            logger.warning(f"No task ID found for notification {notification_id} to cancel")
        
        notification.status = NotificationStatus.CANCELLED
        repository.commit()
        
        logger.info(f"Cancelled notification {notification_id}")

        return True
    finally:
        session.close()
