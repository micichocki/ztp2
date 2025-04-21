import pytz
from datetime import datetime
from exception import ValidationError
from models import NotificationRequest


class TimeZonePolicy:
    def validate(self, notification: NotificationRequest):
        if notification.timezone not in pytz.all_timezones:
            error_msg = f"Invalid timezone provided: {notification.timezone}"
            raise ValidationError(error_msg)


class TimeRangePolicy:
    def validate(self, notification: NotificationRequest):
        if notification.scheduled_time:
            try:
                scheduled_time = pytz.timezone(notification.timezone).localize(
                    datetime.fromisoformat(notification.scheduled_time))
            except ValueError:
                raise ValidationError(f"Invalid scheduled time format: {notification.scheduled_time}")

            current_time = datetime.now(pytz.timezone(notification.timezone))
            if scheduled_time < current_time:
                raise ValidationError("Scheduled time cannot be in the past for the specified timezone.")
