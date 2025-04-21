import logging
from datetime import datetime
from typing import Dict, Optional, Any

from fastapi import FastAPI, HTTPException, Query, Request, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from models import db_session
from service import NotificationService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Notification Service API",
    description="API for scheduling and managing notifications",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = db_session()
    try:
        yield db
    finally:
        db.close()

class NotificationRequest(BaseModel):
    recipient_id: str
    content: str
    timezone: str = "UTC"
    scheduled_time: Optional[str] = None

class NotificationResponse(BaseModel):
    status: str
    notification_id: str
    message: str

@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.post("/notifications/push", response_model=NotificationResponse, tags=["Notifications"])
def schedule_push_notification(notification: NotificationRequest):
    try:
        notification_id = NotificationService.schedule_push_notification(
            recipient_id=notification.recipient_id,
            content=notification.content,
            timezone=notification.timezone,
            scheduled_time=notification.scheduled_time
        )
        
        return {
            "status": "success",
            "notification_id": notification_id,
            "message": "Push notification scheduled"
        }
        
    except Exception as e:
        logger.error(f"Error scheduling push notification: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/notifications/email", response_model=NotificationResponse, tags=["Notifications"])
def schedule_email_notification(notification: NotificationRequest):
    try:
        notification_id = NotificationService.schedule_email_notification(
            recipient_id=notification.recipient_id,
            content=notification.content,
            timezone=notification.timezone,
            scheduled_time=notification.scheduled_time
        )
        
        return {
            "status": "success",
            "notification_id": notification_id,
            "message": "Email notification scheduled"
        }
        
    except Exception as e:
        logger.error(f"Error scheduling email notification: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/notifications/{notification_id}", tags=["Notifications"])
def get_notification(notification_id: str):
    try:
        notification_status = NotificationService.get_notification_status(notification_id)
        if "error" in notification_status:
            raise HTTPException(status_code=404, detail=notification_status["error"])
        return notification_status
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving notification {notification_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/notifications/{notification_id}/force", response_model=Dict[str, Any], tags=["Notifications"])
def force_notification_delivery(notification_id: str):
    try:
        result = NotificationService.force_delivery(notification_id)
        if "error" in result:
            status_code = 404 if result["error"] == "Notification not found" else 400
            raise HTTPException(status_code=status_code, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error forcing delivery of notification {notification_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/notifications/{notification_id}/cancel", response_model=Dict[str, Any], tags=["Notifications"])
def cancel_notification(notification_id: str):
    try:
        result = NotificationService.cancel_notification(notification_id)
        if "error" in result:
            status_code = 404 if result["error"] == "Notification not found" else 400
            raise HTTPException(status_code=status_code, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling notification {notification_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/notifications", tags=["Notifications"])
def list_notifications(
    status: Optional[str] = None,
    timezone: Optional[str] = None,
    recipient_id: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    try:
        notifications = NotificationService.list_notifications(
            status=status,
            timezone=timezone,
            recipient_id=recipient_id,
            limit=limit,
            offset=offset
        )
        
        return {
            "count": len(notifications),
            "notifications": notifications
        }
    except Exception as e:
        logger.error(f"Error listing notifications: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metrics", tags=["Metrics"])
def get_metrics(
    server: Optional[str] = None,
    channel: Optional[str] = None,
    period: Optional[int] = None
):
    try:
        if period is not None and period <= 0:
            raise HTTPException(status_code=400, detail="Period must be a positive integer")
        
        metrics = NotificationService.get_metrics(
            server_id=server,
            channel=channel,
            time_period=period
        )
        
        return metrics
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.middleware("http")
async def db_session_middleware(request: Request, call_next):
    response = Response("Internal server error", status_code=500)
    try:
        response = await call_next(request)
    finally:
        db_session.remove()
    return response


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=5000, reload=True)
