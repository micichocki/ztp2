import uuid
from datetime import datetime
from enum import Enum
import pytz
from typing import Optional, List
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
    priority = Column(Integer, nullable=False, default=5)  # Add priority field

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
        task_id: Optional[str] = None,
        priority: int = 5  # Default priority
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
            task_id=task_id,
            priority=priority
        )
    
    @property
    def created_at_iso(self) -> str:
        return self.created_at.isoformat()
    
    @property
    def scheduled_time_iso(self) -> str:
        return self.scheduled_time.isoformat()


class NotificationRequest(BaseModel):
    recipient_id: str = Field(..., description="ID of the notification recipient")
    content: str = Field(..., description="Content of the notification")
    timezone: str = Field(default="UTC", description="Timezone for scheduled delivery")
    scheduled_time: Optional[str] = Field(default=None, description="ISO formatted scheduled delivery time")
    priority: int = Field(default=5, ge=1, le=10, description="Priority of the notification (1-10)")


class NotificationResponse(BaseModel):
    id: str
    recipient_id: str
    content: str
    channel: str
    status: str
    created_at: datetime
    scheduled_time: datetime
    timezone: str
    attempt_count: int
    task_id: Optional[str] = None

    class Config:
        from_attributes = True

class NotificationListResponse(BaseModel):
    count: int
    notifications: List[NotificationResponse]


class ScheduleResponse(BaseModel):
    task_id: str
    status: str
    message: str


class ActionResponse(BaseModel):
    status: str
    message: str
    notification_id: str
    task_id: str
