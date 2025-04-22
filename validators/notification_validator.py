from typing import List
from exceptions.exception import ValidationError
from models import NotificationRequest
from policy import TimeZonePolicy, TimeRangePolicy, PriorityPolicy, ContentLengthPolicy, ValidationPolicy


class NotificationValidator:
    def __init__(self, notification: NotificationRequest):
        self.notification = notification
        self.policies: List[ValidationPolicy] = [
            TimeZonePolicy(),
            TimeRangePolicy(),
            PriorityPolicy(),
            ContentLengthPolicy(),
        ]

    def validate(self) -> None:
        errors = []
        
        for policy in self.policies:
            try:
                policy.validate(self.notification)
            except ValidationError as e:
                errors.append(str(e))
        
        if errors:
            error_message = "; ".join(errors)
            raise ValidationError(f"Validation failed: {error_message}")
