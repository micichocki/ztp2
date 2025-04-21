from models import NotificationRequest
from policy import TimezonePolicy


class NotificationValidator:
    def __init__(self, notification: NotificationRequest):
        self.notification = notification
        self.policies = [
            TimezonePolicy(),
        ]

    def validate(self):
        for policy in self.policies:
            try:
                policy.validate(self.notification)
            except ValueError as e:
                raise ValueError(f"Validation failed: {e}")