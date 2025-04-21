class NotificationNotFoundException(Exception):
    """Exception raised when a notification is not found."""
    pass

class InvalidNotificationStateException(Exception):
    """Exception raised when a notification is in an invalid state for the operation."""
    pass