from typing import List

from fastapi import APIRouter
from controller import NotificationController, MetricsController
from models import NotificationResponse, ScheduleResponse, ActionResponse
from repositories.notification_repository import NotificationRepository
from service import NotificationService

api_router = APIRouter(prefix="/api")

notification_repository = NotificationRepository()
notification_service = NotificationService(notification_repository)

notification_controller = NotificationController(notification_service)
metrics_controller = MetricsController(notification_service)

notification_router = APIRouter(prefix="/notifications", tags=["Notifications"])
metrics_router = APIRouter(prefix="/metrics", tags=["Metrics"])

notification_router.add_api_route("/push", notification_controller.create_push_notification, methods=["POST"], status_code=201, response_model=ScheduleResponse)
notification_router.add_api_route("/email", notification_controller.create_email_notification, methods=["POST"], status_code=201, response_model=ScheduleResponse)
notification_router.add_api_route("/{notification_id}", notification_controller.get_notification, methods=["GET"], response_model=NotificationResponse)
notification_router.add_api_route("/", notification_controller.list_notifications, methods=["GET"], response_model=List[NotificationResponse])
notification_router.add_api_route("/{notification_id}/force", notification_controller.force_notification_delivery, methods=["POST"], response_model=ActionResponse)
notification_router.add_api_route("/{notification_id}/cancel", notification_controller.cancel_notification, methods=["POST"], response_model=ActionResponse)

metrics_router.add_api_route("/", metrics_controller.get_metrics, methods=["GET"])

api_router.include_router(notification_router)
api_router.include_router(metrics_router)

app_router = APIRouter()
app_router.include_router(api_router)
