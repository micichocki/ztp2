import logging
import random
import pytz
import time
from datetime import datetime
from celery.exceptions import MaxRetriesExceededError
from typing import Optional, Callable, Union, Any

from celery_app import app
from models import Notification, NotificationStatus, DeliveryChannel, db_session
from config import MAX_RETRY_ATTEMPTS, RETRY_DELAY
from metrics import metrics

logger = logging.getLogger(__name__)


class NotificationDeliveryService:

    @staticmethod
    def deliver_push(notification: Notification) -> bool:
        logger.info(f"Sending PUSH notification {notification.id} to {notification.recipient_id}")
        
        processing_time = random.uniform(8.0, 12.0)
        
        for i in range(10):
            time.sleep(processing_time / 10)
            print("Processsing...")
        
        if random.random() < 0.5:
            return True
        raise Exception("Random delivery failure (50% chance)")

    @staticmethod
    def deliver_email(notification: Notification) -> bool:
        logger.info(f"Sending EMAIL notification {notification.id} to {notification.recipient_id}")

        processing_time = random.uniform(8.0, 12.0)
        for i in range(10):
            time.sleep(processing_time / 10)
            print("Processsing...")
        
        if random.random() < 0.5:
            return True
        raise Exception("Random delivery failure (50% chance)")

    @classmethod
    def get_delivery_method(cls, channel: DeliveryChannel) -> Callable[[Notification], bool]:
        delivery_methods = {
            DeliveryChannel.PUSH: cls.deliver_push,
            DeliveryChannel.EMAIL: cls.deliver_email,
        }
        
        if channel not in delivery_methods:
            raise ValueError(f"Unsupported channel: {channel}")
        
        return delivery_methods[channel]


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
        
        metrics.record_notification(
            server_id=task_instance.request.hostname,
            channel=channel,
            status=NotificationStatus.PROCESSING
        )

        try:
            delivery_method = NotificationDeliveryService.get_delivery_method(channel)
            delivery_successful = delivery_method(notification)
            
            if delivery_successful:
                logger.info(f"Successfully delivered {channel.name} notification {notification_id}")
                notification.status = NotificationStatus.DELIVERED
                session.commit()
                
                metrics.record_notification(
                    server_id=task_instance.request.hostname,
                    channel=channel,
                    status=NotificationStatus.DELIVERED
                )
                return True
                
        except Exception as e:
            notification.status = NotificationStatus.FAILED
            notification.attempt_count += 1
            session.commit()
            
            logger.error(f"Failed to deliver {channel.name} notification {notification_id}: {str(e)}")
            
            metrics.record_notification(
                server_id=task_instance.request.hostname,
                channel=channel,
                status=NotificationStatus.FAILED
            )

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

        server_id = getattr(app, 'current_worker', None)
        server_id = server_id.hostname if server_id else 'scheduler'
        
        metrics.record_notification(
            server_id=server_id,
            channel=channel,
            status=NotificationStatus.SCHEDULED
        )

        if scheduled_time:
            local_tz = pytz.timezone(timezone)
            dt = datetime.fromisoformat(scheduled_time)
            if dt.tzinfo is None:
                dt = local_tz.localize(dt)
            scheduled_dt = dt.astimezone(pytz.UTC)
        else:
            scheduled_dt = datetime.now(pytz.UTC)

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
            routing_key=channel
        )
        
        notification.task_id = task.id
        session.commit()
        logger.info(f"Stored task ID {task.id} for notification {notification_id}")

        logger.info(f"Scheduled notification {notification_id} with task {task.id} for delivery at {scheduled_dt}")
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
        
        inspector = app.control.inspect()
        reserved_tasks = inspector.reserved()
        scheduled_tasks = inspector.scheduled()
        
        if reserved_tasks:
            for worker, tasks in reserved_tasks.items():
                for task in tasks:
                    if task['id'] == task_id:
                        logger.info(f"Found reserved task {task_id} on worker {worker}, forcing removal")
                        app.control.terminate(task_id, signal='SIGKILL')
        
        if scheduled_tasks:
            for worker, tasks in scheduled_tasks.items():
                for task in tasks:
                    if task['id'] == task_id:
                        logger.info(f"Found scheduled task {task_id} on worker {worker}, forcing removal")
                        app.control.terminate(task_id, signal='SIGKILL')
        
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
            routing_key=channel
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
        
        server_id = getattr(app, 'current_worker', None)
        server_id = server_id.hostname if server_id else 'scheduler'
        
        metrics.record_notification(
            server_id=server_id,
            channel=notification.channel,
            status=NotificationStatus.CANCELLED
        )
        
        return True
    finally:
        session.close()

