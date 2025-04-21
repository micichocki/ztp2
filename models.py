import uuid
from datetime import datetime
from enum import Enum
import pytz
from typing import Optional, Self, List, Dict, Any
from sqlalchemy import Column, String, Integer, DateTime, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from config import DATABASE_URL
from pydantic import BaseModel, Field

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db_session = scoped_session(SessionLocal)
Base = declarative_base()


class DeliveryChannel(str, Enum):
    PUSH = "push"
    EMAIL = "email"


class NotificationStatus(str, Enum):
    SCHEDULED = "scheduled"
    PROCESSING = "processing"
    DELIVERED = "delivered"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String, primary_key=True)
    recipient_id = Column(String, nullable=False)
    content = Column(String, nullable=False)
    channel = Column(String, nullable=False)
    timezone = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    scheduled_time = Column(DateTime(timezone=True), nullable=False)
    status = Column(String, nullable=False)
    attempt_count = Column(Integer, nullable=False, default=0)
    task_id = Column(String, nullable=True)

    def __init__(
        self, 
        recipient_id: str, 
        content: str, 
        channel: DeliveryChannel, 
        timezone: str = "UTC",
        scheduled_time: Optional[str] = None, 
        id: Optional[str] = None, 
        status: NotificationStatus = NotificationStatus.SCHEDULED,
        attempt_count: int = 0,
        task_id: Optional[str] = None  # Added task_id parameter
    ):
        current_time = datetime.now(pytz.UTC)
        scheduled_datetime = (
            datetime.fromisoformat(scheduled_time) if isinstance(scheduled_time, str) and scheduled_time 
            else current_time
        )
        
        super().__init__(
            id=id or str(uuid.uuid4()),
            recipient_id=recipient_id,
            content=content,
            channel=channel,
            timezone=timezone,
            created_at=current_time,
            scheduled_time=scheduled_datetime,
            status=status,
            attempt_count=attempt_count,
            task_id=task_id  # Initialize task_id
        )
    
    @property
    def created_at_iso(self) -> str:
        return self.created_at.isoformat()
    
    @property
    def scheduled_time_iso(self) -> str:
        return self.scheduled_time.isoformat()

    def save(self) -> Self:
        session = db_session()
        try:
            existing = session.query(Notification).filter(Notification.id == self.id).first()
            
            if existing:
                for key, value in vars(self).items():
                    if key != '_sa_instance_state':
                        setattr(existing, key, value)
            else:
                session.add(self)
                
            session.commit()
            return self
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    @classmethod
    def get(cls, notification_id: str) -> Optional['Notification']:
        """
        DEPRECATED: This method can lead to detached instance errors.
        Use a proper session context instead and query directly.
        """
        session = db_session()
        try:
            notification = session.query(cls).filter(cls.id == notification_id).first()
            return notification
        finally:
            session.close()

    def update_status(self, status: NotificationStatus, increment_attempts: bool = False) -> Self:
        self.status = status
        if increment_attempts:
            self.attempt_count += 1
        self.save()
        return self

class NotificationRequest(BaseModel):
    recipient_id: str = Field(..., description="ID of the notification recipient")
    content: str = Field(..., description="Content of the notification")
    timezone: str = Field(default="UTC", description="Timezone for scheduled delivery")
    scheduled_time: Optional[str] = Field(default=None, description="ISO formatted scheduled delivery time")

class NotificationResponse(BaseModel):
    notification_id: str
    status: str

class NotificationStatusResponse(BaseModel):
    id: str
    recipient_id: str
    content: str
    channel: str
    status: str
    created_at: str
    scheduled_time: str
    timezone: str
    local_scheduled_time: str
    appropriate_delivery: bool
    estimated_delivery_time: str
    attempt_count: int

class NotificationListResponse(BaseModel):
    count: int
    notifications: List[Dict[str, Any]]

class TaskResponse(BaseModel):
    status: str
    message: str
    notification_id: str
    task_id: str
