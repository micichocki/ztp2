import pytz
from datetime import datetime
from typing import Protocol
from exceptions.exception import ValidationError
from models import NotificationRequest


class ValidationPolicy(Protocol):
    def validate(self, notification: NotificationRequest) -> None:
        ...


class TimeZonePolicy:
    def validate(self, notification: NotificationRequest) -> None:
        if notification.timezone not in pytz.all_timezones:
            error_msg = f"Invalid timezone provided: {notification.timezone}"
            raise ValidationError(error_msg)


class TimeRangePolicy:
    def validate(self, notification: NotificationRequest) -> None:
        if notification.scheduled_time:
            try:
                scheduled_time = pytz.timezone(notification.timezone).localize(
                    datetime.fromisoformat(notification.scheduled_time))
            except ValueError:
                raise ValidationError(f"Invalid scheduled time format: {notification.scheduled_time}")

            current_time = datetime.now(pytz.timezone(notification.timezone))
            if scheduled_time < current_time:
                raise ValidationError("Scheduled time cannot be in the past for the specified timezone.")


class PriorityPolicy:
    MIN_PRIORITY = 1
    MAX_PRIORITY = 10
    
    def validate(self, notification: NotificationRequest) -> None:
        if not isinstance(notification.priority, int):
            raise ValidationError(f"Priority must be an integer, got {type(notification.priority).__name__}")
            
        if notification.priority < self.MIN_PRIORITY or notification.priority > self.MAX_PRIORITY:
            raise ValidationError(
                f"Priority must be between {self.MIN_PRIORITY} and {self.MAX_PRIORITY}, got {notification.priority}"
            )


class ContentLengthPolicy:
    MAX_LENGTH = 2000
    
    def validate(self, notification: NotificationRequest) -> None:
        if not notification.content:
            raise ValidationError("Notification content cannot be empty")
            
        if len(notification.content) > self.MAX_LENGTH:
            raise ValidationError(
                f"Notification content exceeds maximum length of {self.MAX_LENGTH} characters"
            )
