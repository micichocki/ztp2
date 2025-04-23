import logging
from typing import List, Optional, Type
from sqlalchemy.orm import Session

from models import Notification, db_session

logger = logging.getLogger(__name__)

class NotificationRepository:
    def __init__(self, session=None):
        self.session = session

    def _get_session(self) -> Session:
        if self.session:
            return self.session
        return db_session()

    def get_by_id(self, notification_id: str) -> Optional[Notification]:
        session = self._get_session()
        try:
            notification = session.query(Notification).filter(Notification.id == notification_id).first()
            return notification
        finally:
            if not self.session:
                session.close()
    
    def save(self, notification: Notification) -> None:
        session = self._get_session()
        try:
            session.add(notification)
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving notification: {str(e)}")
            raise
        finally:
            if not self.session:
                session.close()
    
    def commit(self) -> None:
        session = self._get_session()
        try:
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating notification: {str(e)}")
            raise
        finally:
            if not self.session:
                session.close()
