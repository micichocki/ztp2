from fastapi import APIRouter
from controller import NotificationController, MetricsController, HealthController

api_router = APIRouter(prefix="/api")

notification_router = APIRouter(prefix="/notifications", tags=["Notifications"])
metrics_router = APIRouter(prefix="/metrics", tags=["Metrics"])
health_router = APIRouter(tags=["Health"])

notification_router.add_api_route("/push", NotificationController.create_push_notification, methods=["POST"], status_code=201, response_model_exclude_none=True)
notification_router.add_api_route("/email", NotificationController.create_email_notification, methods=["POST"], status_code=201, response_model_exclude_none=True)
notification_router.add_api_route("/{notification_id}", NotificationController.get_notification, methods=["GET"])
notification_router.add_api_route("/{notification_id}/force", NotificationController.force_notification_delivery, methods=["POST"])
notification_router.add_api_route("/{notification_id}/cancel", NotificationController.cancel_notification, methods=["POST"])
notification_router.add_api_route("/", NotificationController.list_notifications, methods=["GET"])

metrics_router.add_api_route("/", MetricsController.get_metrics, methods=["GET"])

health_router.add_api_route("/health", HealthController.health_check, methods=["GET"])

api_router.include_router(notification_router)
api_router.include_router(metrics_router)

app_router = APIRouter()
app_router.include_router(api_router)
app_router.include_router(health_router)
