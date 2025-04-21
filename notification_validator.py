from exception import ValidationError
from models import NotificationRequest
from policy import TimeZonePolicy, TimeRangePolicy


class NotificationValidator:
    def __init__(self, notification: NotificationRequest):
        self.notification = notification
        self.policies = [
            TimeZonePolicy(),
            TimeRangePolicy(),
        ]

    def validate(self):
        try:
            for policy in self.policies:
                policy.validate(self.notification)
        except ValidationError as e:
            raise ValidationError(f"Validation failed: {str(e)}")
