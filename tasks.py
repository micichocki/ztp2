import logging
import random
import pytz
import time
from datetime import datetime, timedelta
from celery.exceptions import MaxRetriesExceededError
from typing import Optional, Callable, Union, Any

from celery_app import app
from models import Notification, NotificationStatus, DeliveryChannel, db_session
from config import MAX_RETRY_ATTEMPTS, RETRY_DELAY, APPROPRIATE_HOURS_START, APPROPRIATE_HOURS_END

logger = logging.getLogger(__name__)


class NotificationDeliveryService:

    @staticmethod
    def deliver_notification(notification: Notification, channel: DeliveryChannel) -> bool:
        logger.info(f"Sending {channel.name} notification {notification.id} to {notification.recipient_id}")

        processing_time = random.uniform(5.0, 8.0)
        for i in range(10):
            time.sleep(processing_time / 10)
            logger.info("Processing...")

        if random.random() < 0.5:
            return True
        raise Exception(f"Random delivery failure (50% chance) for {channel.name}")

    @classmethod
    def get_delivery_method(cls, channel: DeliveryChannel) -> Callable[[Any], bool]:
        if channel not in [DeliveryChannel.PUSH, DeliveryChannel.EMAIL]:
            raise ValueError(f"Unsupported channel: {channel}")

        return lambda notification: cls.deliver_notification(notification, channel)

def _handle_notification_delivery(
    task_instance: Any,
    notification_id: str,
    channel: DeliveryChannel
) -> Optional[bool]:
    session = db_session()
    try:
        notification = session.query(Notification).filter(Notification.id == notification_id).first()
        if not notification:
            logger.error(f"Notification {notification_id} not found")
            return False

        if notification.status == NotificationStatus.CANCELLED:
            logger.info(f"Notification {notification_id} has been cancelled, skipping delivery")
            return False

        notification.status = NotificationStatus.PROCESSING
        session.commit()

        try:
            delivery_method = NotificationDeliveryService.get_delivery_method(channel)
            delivery_successful = delivery_method(notification)
            
            if delivery_successful:
                logger.info(f"Successfully delivered {channel.name} notification {notification_id} content: {notification.content}")
                notification.status = NotificationStatus.DELIVERED
                session.commit()
                return True
                
        except Exception as e:
            notification.status = NotificationStatus.FAILED
            notification.attempt_count += 1
            session.commit()
            
            logger.error(f"Failed to deliver {channel.name} notification {notification_id}: {str(e)}")


            if notification.attempt_count < MAX_RETRY_ATTEMPTS:
                logger.info(f"Retrying {channel.name} notification {notification_id}, attempt {notification.attempt_count}")
                raise task_instance.retry(exc=e, countdown=RETRY_DELAY)
            else:
                logger.error(f"Max retries exceeded for {channel.name} notification {notification_id}")
                raise MaxRetriesExceededError()
        
        return False
        
    finally:
        session.close()


@app.task(bind=True, max_retries=MAX_RETRY_ATTEMPTS)
def send_push_notification(self, notification_id: str) -> Optional[bool]:
    return _handle_notification_delivery(self, notification_id, DeliveryChannel.PUSH)


@app.task(bind=True, max_retries=MAX_RETRY_ATTEMPTS)
def send_email_notification(self, notification_id: str) -> Optional[bool]:
    return _handle_notification_delivery(self, notification_id, DeliveryChannel.EMAIL)


def is_within_appropriate_hours(dt: datetime, timezone_str: str) -> bool:
    if dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)
    
    local_tz = pytz.timezone(timezone_str)
    local_dt = dt.astimezone(local_tz)
    
    local_hour = local_dt.hour
    
    logger.info(f"Checking if {local_dt.isoformat()} (hour: {local_hour}) is within appropriate hours "
                f"({APPROPRIATE_HOURS_START}-{APPROPRIATE_HOURS_END}) in timezone {timezone_str}")
    
    return APPROPRIATE_HOURS_START <= local_hour < APPROPRIATE_HOURS_END


def get_next_appropriate_time(dt: datetime, timezone_str: str) -> datetime:
    if dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)
    
    local_tz = pytz.timezone(timezone_str)
    local_dt = dt.astimezone(local_tz)
    
    logger.info(f"Finding next appropriate time for {local_dt.isoformat()} in timezone {timezone_str}")
    
    if local_dt.hour >= APPROPRIATE_HOURS_END or local_dt.hour < APPROPRIATE_HOURS_START:
        if local_dt.hour >= APPROPRIATE_HOURS_END:
            local_dt = local_dt + timedelta(days=1)
            logger.info(f"After hours: adding a day to schedule for tomorrow")
        
        local_dt = local_dt.replace(hour=APPROPRIATE_HOURS_START, minute=0, second=0, microsecond=0)
        logger.info(f"Adjusted to appropriate hours start: {local_dt.isoformat()}")
    
    utc_dt = local_dt.astimezone(pytz.UTC)
    logger.info(f"Next appropriate time in UTC: {utc_dt.isoformat()}")
    return utc_dt


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
    try:
        session.add(notification)
        session.commit()
        
        logger.info(f"Created notification {notification_id} for delivery via {channel}")
        if scheduled_time:
            dt = datetime.fromisoformat(scheduled_time)
            if dt.tzinfo is None:
                local_tz = pytz.timezone(timezone)
                dt = local_tz.localize(dt)
                logger.info(f"Localized naive datetime to {timezone}: {dt.isoformat()}")
            scheduled_dt = dt
            logger.info(f"Processing notification with explicit scheduled time: {scheduled_dt.isoformat()}")
        else:
            scheduled_dt = datetime.now(pytz.UTC)
            logger.info(f"No scheduled time provided, using current time: {scheduled_dt.isoformat()}")
        
        if not is_within_appropriate_hours(scheduled_dt, timezone):
            logger.info(f"Scheduled time {scheduled_dt.isoformat()} is outside appropriate hours "
                        f"({APPROPRIATE_HOURS_START}-{APPROPRIATE_HOURS_END}) in timezone {timezone}")
            
            scheduled_dt = get_next_appropriate_time(scheduled_dt, timezone)
            
            notification.scheduled_time = scheduled_dt
            session.commit()
            
            logger.info(f"Notification {notification_id} rescheduled for {scheduled_dt.isoformat()}")

        channel_tasks = {
            DeliveryChannel.PUSH: send_push_notification,
            DeliveryChannel.EMAIL: send_email_notification,
        }
        
        if channel not in channel_tasks:
            logger.error(f"Unsupported channel: {channel}")
            return False

        task = channel_tasks[channel].apply_async(
            args=[notification_id],
            eta=scheduled_dt,
            queue='notifications',
        )
        
        notification.task_id = task.id
        session.commit()
        logger.info(f"Stored task ID {task.id} for notification {notification_id}")

        logger.info(f"Scheduled notification {notification_id} with task {task.id} for delivery at {scheduled_dt.isoformat()}")
        return task.id
    except Exception as e:
        session.rollback()
        logger.error(f"Error scheduling notification: {str(e)}")
        raise
    finally:
        session.close()


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


@app.task
def force_immediate_delivery(notification_id: str) -> Optional[bool]:
    session = db_session()
    try:
        notification = session.query(Notification).filter(Notification.id == notification_id).first()
        if not notification:
            logger.error(f"Notification {notification_id} not found")
            return False

        if notification.status != NotificationStatus.SCHEDULED:
            logger.warning(f"Cannot force delivery for notification {notification_id} with status {notification.status}")
            return False

        original_task_id = notification.task_id
        if original_task_id:
            logger.info(f"Revoking existing task {original_task_id} for notification {notification_id}")
            if not revoke_task(original_task_id):
                logger.warning(f"Failed to revoke task {original_task_id}, proceeding with immediate delivery anyway")
        else:
            logger.warning(f"No task ID found for notification {notification_id}")
        
        notification.status = NotificationStatus.PROCESSING
        session.commit()

        logger.info(f"Forcing immediate delivery of notification {notification_id}")

        channel = notification.channel
        channel_tasks = {
            DeliveryChannel.PUSH: send_push_notification,
            DeliveryChannel.EMAIL: send_email_notification,
        }

        if channel not in channel_tasks:
            logger.error(f"Unsupported channel: {channel}")
            return False

        task = channel_tasks[channel].apply_async(
            args=[notification_id], 
            countdown=0,
            queue='notifications',
        )
        
        notification.task_id = task.id
        session.commit()
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
    try:
        notification = session.query(Notification).filter(Notification.id == notification_id).first()
        if not notification:
            logger.error(f"Notification {notification_id} not found")
            return False
        
        if notification.status != NotificationStatus.SCHEDULED:
            logger.warning(f"Cannot cancel notification {notification_id} with status {notification.status}")
            return False
        
        original_task_id = notification.task_id
        if original_task_id:
            logger.info(f"Revoking task {original_task_id} for cancelled notification {notification_id}")
            if not revoke_task(original_task_id):
                logger.warning(f"Failed to revoke task {original_task_id} directly, trying alternative methods")
                
                try:
                    task = app.AsyncResult(original_task_id)
                    task.revoke(terminate=True, signal='SIGKILL')
                    logger.info(f"Revoked task {original_task_id} through AsyncResult")
                except Exception as e:
                    logger.error(f"Alternative revocation also failed: {str(e)}")
        else:
            logger.warning(f"No task ID found for notification {notification_id} to cancel")
        
        notification.status = NotificationStatus.CANCELLED
        session.commit()
        
        logger.info(f"Cancelled notification {notification_id}")

        return True
    finally:
        session.close()

