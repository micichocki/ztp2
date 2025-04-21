import logging
import random
import pytz
from datetime import datetime
from celery.exceptions import MaxRetriesExceededError
from typing import Optional

from celery_app import app
from models import Notification, NotificationStatus, DeliveryChannel, db_session
from config import MAX_RETRY_ATTEMPTS, RETRY_DELAY
from metrics import metrics

logger = logging.getLogger(__name__)

class NotificationDeliveryService:
    """Service for handling notification delivery logic"""
    
    @staticmethod
    def deliver_push(notification: Notification) -> bool:
        """Business logic for push notification delivery"""
        logger.info(f"Sending PUSH notification {notification.id} to {notification.recipient_id}")
        
        if random.random() < 0.5:
            return True
        else:
            raise Exception("Random delivery failure (50% chance)")
    
    @staticmethod
    def deliver_email(notification: Notification) -> bool:
        """Business logic for email notification delivery"""
        logger.info(f"Sending EMAIL notification {notification.id} to {notification.recipient_id}")
        
        if random.random() < 0.5:
            return True
        else:
            raise Exception("Random delivery failure (50% chance)")


@app.task(bind=True, max_retries=MAX_RETRY_ATTEMPTS)
def send_push_notification(self, notification_id: str) -> None|bool:
    """Celery task for sending push notifications"""
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
            server_id=self.request.hostname,
            channel=DeliveryChannel.PUSH,
            status=NotificationStatus.PROCESSING
        )

        try:
            delivery_successful = NotificationDeliveryService.deliver_push(notification)
            
            if delivery_successful:
                logger.info(f"Successfully delivered PUSH notification {notification_id}")
                notification.status = NotificationStatus.DELIVERED
                session.commit()
                
                metrics.record_notification(
                    server_id=self.request.hostname,
                    channel=DeliveryChannel.PUSH,
                    status=NotificationStatus.DELIVERED
                )
                return True

        except Exception as e:
            notification.status = NotificationStatus.FAILED
            notification.attempt_count += 1
            session.commit()
            
            logger.error(f"Failed to deliver PUSH notification {notification_id}: {str(e)}")
            
            metrics.record_notification(
                server_id=self.request.hostname,
                channel=DeliveryChannel.PUSH,
                status=NotificationStatus.FAILED
            )

            if notification.attempt_count < MAX_RETRY_ATTEMPTS:
                logger.info(f"Retrying PUSH notification {notification_id}, attempt {notification.attempt_count}")
                raise self.retry(exc=e, countdown=RETRY_DELAY)
            else:
                logger.error(f"Max retries exceeded for PUSH notification {notification_id}")
                raise MaxRetriesExceededError()
        
        return False
        
    finally:
        session.close()


@app.task(bind=True, max_retries=MAX_RETRY_ATTEMPTS)
def send_email_notification(self, notification_id: str) -> None|bool:
    """Celery task for sending email notifications"""
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
            server_id=self.request.hostname,
            channel=DeliveryChannel.EMAIL,
            status=NotificationStatus.PROCESSING
        )

        try:
            delivery_successful = NotificationDeliveryService.deliver_email(notification)
            
            if delivery_successful:
                logger.info(f"Successfully delivered EMAIL notification {notification_id}")
                notification.status = NotificationStatus.DELIVERED
                session.commit()
                
                metrics.record_notification(
                    server_id=self.request.hostname,
                    channel=DeliveryChannel.EMAIL,
                    status=NotificationStatus.DELIVERED
                )
                return True
                
        except Exception as e:
            notification.status = NotificationStatus.FAILED
            notification.attempt_count += 1
            session.commit()
            
            logger.error(f"Failed to deliver EMAIL notification {notification_id}: {str(e)}")
            
            metrics.record_notification(
                server_id=self.request.hostname,
                channel=DeliveryChannel.EMAIL,
                status=NotificationStatus.FAILED
            )

            if notification.attempt_count < MAX_RETRY_ATTEMPTS:
                logger.info(f"Retrying EMAIL notification {notification_id}, attempt {notification.attempt_count}")
                raise self.retry(exc=e, countdown=RETRY_DELAY)
            else:
                logger.error(f"Max retries exceeded for EMAIL notification {notification_id}")
                raise MaxRetriesExceededError()
        
        return False
        
    finally:
        session.close()


@app.task
def schedule_notification(
        recipient_id: str,
        content: str,
        channel: DeliveryChannel,
        timezone: str = "UTC",
        scheduled_time: Optional[str] = None
) -> str|bool|None:
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

        metrics.record_notification(
            server_id=app.current_worker.hostname if hasattr(app, 'current_worker') else 'scheduler',
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

        if channel == DeliveryChannel.PUSH:
            task = send_push_notification
        elif channel == DeliveryChannel.EMAIL:
            task = send_email_notification
        else:
            logger.error(f"Unsupported channel: {channel}")
            return False

        task.apply_async(
            args=[notification_id],
            eta=scheduled_dt,
            routing_key=channel
        )

        logger.info(f"Scheduled notification {notification_id} for delivery at {scheduled_dt}")
        return notification_id
    except Exception as e:
        session.rollback()
        logger.error(f"Error scheduling notification: {str(e)}")
        raise
    finally:
        session.close()


@app.task
def force_immediate_delivery(notification_id: str) -> None|bool:
    """Force immediate delivery of a notification"""
    session = db_session()
    try:
        notification = session.query(Notification).filter(Notification.id == notification_id).first()
        if not notification:
            logger.error(f"Notification {notification_id} not found")
            return False
        
        if notification.status != NotificationStatus.SCHEDULED:
            logger.warning(f"Cannot force delivery for notification {notification_id} with status {notification.status}")
            return False
        
        logger.info(f"Forcing immediate delivery of notification {notification_id}")
        
        channel = notification.channel
        
        if channel == DeliveryChannel.PUSH:
            send_push_notification.apply_async(args=[notification_id], countdown=0)
        elif channel == DeliveryChannel.EMAIL:
            send_email_notification.apply_async(args=[notification_id], countdown=0)
        else:
            logger.error(f"Unsupported channel: {channel}")
            return False
        
        return True
    finally:
        session.close()


@app.task
def cancel_notification(notification_id: str) -> bool:
    """Cancel a scheduled notification"""
    session = db_session()
    try:
        notification = session.query(Notification).filter(Notification.id == notification_id).first()
        if not notification:
            logger.error(f"Notification {notification_id} not found")
            return False
        
        if notification.status != NotificationStatus.SCHEDULED:
            logger.warning(f"Cannot cancel notification {notification_id} with status {notification.status}")
            return False
        
        notification.status = NotificationStatus.CANCELLED
        session.commit()
        
        logger.info(f"Cancelled notification {notification_id}")
        
        metrics.record_notification(
            server_id=app.current_worker.hostname if hasattr(app, 'current_worker') else 'scheduler',
            channel=notification.channel,
            status=NotificationStatus.CANCELLED
        )
        
        return True
    finally:
        session.close()
