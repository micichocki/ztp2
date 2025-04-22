import logging
import random
import time
from typing import Callable, Any, Optional

from models import Notification, DeliveryChannel

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

    @staticmethod
    def process_delivery_attempt(
        notification: Notification, 
        channel: DeliveryChannel,
        delivery_method: Callable[[Notification], bool],
        task_instance: Any,
        max_retry_attempts: int,
        retry_delay: int
    ) -> Optional[bool]:
        try:
            delivery_successful = delivery_method(notification)
            
            if delivery_successful:
                logger.info(f"Successfully delivered {channel.name} notification {notification.id} content: {notification.content}")
                return True
                
        except Exception as e:
            notification.attempt_count += 1
            logger.error(f"Failed to deliver {channel.name} notification {notification.id}: {str(e)}")

            if notification.attempt_count < max_retry_attempts:
                logger.info(f"Retrying {channel.name} notification {notification.id}, attempt {notification.attempt_count}")
                raise task_instance.retry(exc=e, countdown=retry_delay)
            else:
                logger.error(f"Max retries exceeded for {channel.name} notification {notification.id}")
                raise
        
        return False
