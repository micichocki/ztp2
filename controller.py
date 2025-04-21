from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query

from models import TaskResponse, NotificationResponse, NotificationRequest, NotificationListResponse
from service import NotificationService

notification_router = APIRouter(prefix="/api/notifications", tags=["notifications"])


class NotificationController:

    @staticmethod
    @notification_router.post("/push", response_model=NotificationResponse, status_code=201)
    async def create_push_notification(request: NotificationRequest):
        notification_id = NotificationService.schedule_push_notification(
            recipient_id=request.recipient_id,
            content=request.content,
            timezone=request.timezone,
            scheduled_time=request.scheduled_time
        )
        
        return {
            'notification_id': notification_id,
            'status': 'scheduled'
        }
    
    @staticmethod
    @notification_router.post("/email", response_model=NotificationResponse, status_code=201)
    async def create_email_notification(request: NotificationRequest):
        notification_id = NotificationService.schedule_email_notification(
            recipient_id=request.recipient_id,
            content=request.content,
            timezone=request.timezone,
            scheduled_time=request.scheduled_time
        )
        
        return {
            'notification_id': notification_id,
            'status': 'scheduled'
        }
    
    @staticmethod
    @notification_router.post("/{notification_id}/force", response_model=TaskResponse)
    async def force_notification_delivery(notification_id: str):
        result = NotificationService.force_delivery(notification_id)
        
        if 'error' in result:
            raise HTTPException(status_code=400, detail=result['error'])
        
        return result
    
    @staticmethod
    @notification_router.post("/{notification_id}/cancel", response_model=TaskResponse)
    async def cancel_notification(notification_id: str):
        result = NotificationService.cancel_notification(notification_id)
        
        if 'error' in result:
            raise HTTPException(status_code=400, detail=result['error'])
        
        return result
    
    @staticmethod
    @notification_router.get("/{notification_id}", response_model=Dict[str, Any])
    async def get_notification(notification_id: str):
        result = NotificationService.get_notification_status(notification_id)
        
        if 'error' in result:
            raise HTTPException(status_code=404, detail=result['error'])
        
        return result
    
    @staticmethod
    @notification_router.get("/", response_model=NotificationListResponse)
    async def list_notifications(
        status: Optional[str] = None,
        timezone: Optional[str] = None,
        recipient_id: Optional[str] = None,
        limit: int = Query(100, ge=1, le=1000),
        offset: int = Query(0, ge=0)
    ):
        notifications = NotificationService.list_notifications(
            status=status,
            timezone=timezone,
            recipient_id=recipient_id,
            limit=limit,
            offset=offset
        )
        
        return {
            'count': len(notifications),
            'notifications': notifications
        }
    
    @staticmethod
    @notification_router.get("/metrics", response_model=Dict[str, Any])
    async def get_metrics(
        server_id: Optional[str] = None,
        channel: Optional[str] = None,
        time_period: Optional[int] = None
    ):
        metrics = NotificationService.get_metrics(
            server_id=server_id,
            channel=channel,
            time_period=time_period
        )
        
        return metrics

notification_controller = NotificationController()
