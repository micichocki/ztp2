import pytz

from models import NotificationRequest


class TimezonePolicy:

    def validate(self, notification: NotificationRequest):
        if notification.timezone not in pytz.all_timezones:
            error_msg = f"Invalid timezone provided: {notification.timezone}"
            raise ValueError(error_msg)