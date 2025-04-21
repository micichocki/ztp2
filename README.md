# Notification System

A scalable, distributed notification system built with FastAPI, Celery, and RabbitMQ that handles push and email notifications with advanced features including scheduling, metrics collection, and delivery time optimization.

## Table of Contents

- [Overview](#overview)
- [System Architecture](#system-architecture)
- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
  - [API Endpoints](#api-endpoints)
  - [Notification Management](#notification-management)
  - [Metrics](#metrics)
- [Worker Configuration](#worker-configuration)
- [Development](#development)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)

## Overview

This notification system provides a robust platform for scheduling and sending notifications through multiple channels. It implements a microservice architecture with dedicated workers for different notification channels, intelligent scheduling with timezone support, and comprehensive metrics collection.

The system uses FastAPI for the REST API, Celery with RabbitMQ for distributed task management, and PostgreSQL for data persistence. It provides HTTP endpoints for scheduling notifications, checking their status, and collecting performance metrics.

## System Architecture

The notification system is composed of several key components:

![System Architecture](https://user-images.githubusercontent.com/placeholder/architecture.png)

1. **API Server (FastAPI)**: Handles HTTP requests for notification management
2. **Task Queue (RabbitMQ)**: Manages task distribution to workers
3. **Workers (Celery)**: Processes notification delivery tasks
   - Push Notification Worker
   - Email Notification Worker
4. **Database (PostgreSQL)**: Stores notification data and status
5. **Metrics Collector**: Tracks performance metrics for the system

### Data Flow

1. Client sends a notification request to the API
2. API server validates the request and schedules a task
3. Task is queued in RabbitMQ
4. Appropriate worker picks up the task
5. Worker attempts to deliver the notification
6. Status and metrics are recorded
7. Client can query notification status or metrics

## Features

- **Multi-channel Support**: Push and email notification channels
- **Scheduled Delivery**: Schedule notifications for future delivery
- **Timezone Awareness**: Respect recipient's timezone for delivery
- **Appropriate Hours Delivery**: Automatically adjust delivery to appropriate hours (8 AM - 10 PM)
- **Retry Mechanism**: Automatic retries with configurable attempts and delays
- **Cancellation**: Cancel scheduled notifications before delivery
- **Force Delivery**: Override scheduling for immediate delivery
- **Metrics Collection**: Detailed metrics on notification status by channel and server
- **Worker Scaling**: Run multiple workers per channel for horizontal scaling
- **API Documentation**: Automatic API documentation with Swagger UI

## Requirements

- Python 3.8+
- PostgreSQL 12+
- RabbitMQ 3.8+
- Docker and Docker Compose (optional for containerized deployment)

## Installation

### Local Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/notification-system.git
   cd notification-system
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up PostgreSQL:
   ```bash
   # Create database and user
   createuser -P ztp2
   createdb -O ztp2 ztp2
   ```

5. Set up RabbitMQ:
   ```bash
   # Install RabbitMQ if not already installed
   # Create vhost and user for the application
   rabbitmqctl add_user ztp2 ztp2
   rabbitmqctl add_vhost ztp2_vhost
   rabbitmqctl set_permissions -p ztp2_vhost ztp2 ".*" ".*" ".*"
   ```

6. Initialize the database:
   ```bash
   python init_db.py
   ```

### Docker Setup

1. Build and start containers:
   ```bash
   docker-compose up -d
   ```

## Configuration

Configuration is managed through environment variables and the `config.py` file.

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://ztp2:ztp2@localhost:5432/ztp2` |
| `CELERY_BROKER_URL` | RabbitMQ connection string | `amqp://ztp2:ztp2@rabbitmq:5672//` |
| `CELERY_RESULT_BACKEND` | Celery result backend | `db+postgresql://ztp2:ztp2@db:5432/ztp2` |
| `METRICS_ENABLED` | Enable metrics collection | `TRUE` |
| `PUSH_METRICS_PORT` | Port for push metrics API | `5001` |
| `EMAIL_METRICS_PORT` | Port for email metrics API | `5002` |
| `FLOWER_PORT` | Port for Flower monitoring | `5555` |
| `FLOWER_HOST` | Host for Flower monitoring | `0.0.0.0` |

### Other Configurations (config.py)

| Parameter | Description | Default |
|-----------|-------------|---------|
| `MAX_RETRY_ATTEMPTS` | Maximum retry attempts for failed tasks | `5` |
| `RETRY_DELAY` | Delay between retries in seconds | `1` |
| `APPROPRIATE_HOURS_START` | Start of appropriate hours for delivery | `8` (8 AM) |
| `APPROPRIATE_HOURS_END` | End of appropriate hours for delivery | `22` (10 PM) |

## Usage

### Starting the System

1. Start the API server:
   ```bash
   uvicorn app:app --host 0.0.0.0 --port 5000 --reload
   ```

2. Start workers:
   ```bash
   # Start push notification worker
   python workers.py push
   
   # Start email notification worker
   python workers.py email
   ```

3. (Optional) Start Flower for monitoring Celery:
   ```bash
   celery -A celery_app.app flower --address=0.0.0.0 --port=5555
   ```

### API Endpoints

The API is documented with Swagger UI, accessible at `http://localhost:5000/docs` when the server is running.

#### Main Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/notifications/push` | POST | Schedule a push notification |
| `/notifications/email` | POST | Schedule an email notification |
| `/notifications/{notification_id}` | GET | Get notification status |
| `/notifications/{notification_id}/force` | POST | Force immediate delivery |
| `/notifications/{notification_id}/cancel` | POST | Cancel scheduled notification |
| `/notifications` | GET | List notifications with filtering |
| `/metrics` | GET | Get system metrics |
| `/health` | GET | Health check endpoint |

### Notification Management

#### Scheduling a Push Notification

```bash
curl -X POST "http://localhost:5000/notifications/push" \
  -H "Content-Type: application/json" \
  -d '{
    "recipient_id": "user123",
    "content": "Your order has been shipped!",
    "timezone": "America/New_York",
    "scheduled_time": "2023-12-01T15:30:00"
  }'
```

Response:
```json
{
  "status": "success",
  "notification_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "message": "Push notification scheduled"
}
```

#### Scheduling an Email Notification

```bash
curl -X POST "http://localhost:5000/notifications/email" \
  -H "Content-Type: application/json" \
  -d '{
    "recipient_id": "user@example.com",
    "content": "Your invoice is ready to view",
    "timezone": "Europe/London",
    "scheduled_time": "2023-12-01T09:00:00"
  }'
```

Response:
```json
{
  "status": "success",
  "notification_id": "e47ac10b-58cc-4372-a567-0e02b2c3d480",
  "message": "Email notification scheduled"
}
```

#### Getting Notification Status

```bash
curl -X GET "http://localhost:5000/notifications/f47ac10b-58cc-4372-a567-0e02b2c3d479"
```

Response:
```json
{
  "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "recipient_id": "user123",
  "content": "Your order has been shipped!",
  "channel": "push",
  "status": "Pending",
  "created_at": "2023-11-30T10:15:30.123456+00:00",
  "scheduled_time": "2023-12-01T20:30:00+00:00",
  "timezone": "America/New_York",
  "local_scheduled_time": "2023-12-01T15:30:00-05:00",
  "appropriate_delivery": true,
  "estimated_delivery_time": "2023-12-01T15:30:00-05:00",
  "attempt_count": 0
}
```

#### Forcing Immediate Delivery

```bash
curl -X POST "http://localhost:5000/notifications/f47ac10b-58cc-4372-a567-0e02b2c3d479/force"
```

Response:
```json
{
  "status": "success",
  "message": "Notification delivery forced",
  "notification_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "task_id": "d47ac10b-58cc-4372-a567-0e02b2c3d481"
}
```

#### Cancelling a Notification

```bash
curl -X POST "http://localhost:5000/notifications/f47ac10b-58cc-4372-a567-0e02b2c3d479/cancel"
```

Response:
```json
{
  "status": "success",
  "message": "Notification cancelled",
  "notification_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "task_id": "c47ac10b-58cc-4372-a567-0e02b2c3d482"
}
```

#### Listing Notifications

```bash
curl -X GET "http://localhost:5000/notifications?status=Pending&limit=10&offset=0"
```

Response:
```json
{
  "count": 2,
  "notifications": [
    {
      "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "recipient_id": "user123",
      "content": "Your order has been shipped!",
      "channel": "push",
      "status": "Pending",
      "created_at": "2023-11-30T10:15:30.123456+00:00",
      "scheduled_time": "2023-12-01T20:30:00+00:00",
      "timezone": "America/New_York",
      "local_scheduled_time": "2023-12-01T15:30:00-05:00",
      "appropriate_delivery": true,
      "attempt_count": 0
    },
    {
      "id": "e47ac10b-58cc-4372-a567-0e02b2c3d480",
      "recipient_id": "user@example.com",
      "content": "Your invoice is ready to view",
      "channel": "email",
      "status": "Pending",
      "created_at": "2023-11-30T11:20:15.654321+00:00",
      "scheduled_time": "2023-12-01T09:00:00+00:00",
      "timezone": "Europe/London",
      "local_scheduled_time": "2023-12-01T09:00:00+00:00",
      "appropriate_delivery": true,
      "attempt_count": 0
    }
  ]
}
```

### Metrics

#### Getting System Metrics

```bash
curl -X GET "http://localhost:5000/metrics?period=3600"
```

Response:
```json
{
  "timestamp": "2023-11-30T12:34:56.789012",
  "servers": {
    "push.worker.hostname": {
      "channels": {
        "push": {
          "total": 120,
          "statuses": {
            "scheduled": 45,
            "processing": 10,
            "delivered": 60,
            "failed": 5
          }
        }
      },
      "total": 120
    },
    "email.worker.hostname": {
      "channels": {
        "email": {
          "total": 85,
          "statuses": {
            "scheduled": 30,
            "processing": 5,
            "delivered": 45,
            "failed": 5
          }
        }
      },
      "total": 85
    }
  },
  "total": 205
}
```

## Worker Configuration

The system uses Celery workers to process notification tasks. There are two types of workers:

1. **Push Notification Worker**: Handles push notifications
2. **Email Notification Worker**: Handles email notifications

Each worker type listens to a specific routing key in the default queue:
- Push workers: routing_key='push'
- Email workers: routing_key='email'

### Starting Workers

```bash
# Start push notification worker
python workers.py push

# Start email notification worker
python workers.py email
```

### Worker Metrics

Each worker type exposes metrics on a separate HTTP port:
- Push worker metrics: http://localhost:5001/metrics
- Email worker metrics: http://localhost:5002/metrics

## Development

### Project Structure

```
notification-system/
├── app.py                # FastAPI application and API endpoints
├── celery_app.py         # Celery application configuration
├── config.py             # System configuration
├── controller.py         # API controllers
├── metrics.py            # Metrics collection
├── models.py             # Database models
├── service.py            # Business logic services
├── tasks.py              # Celery tasks
└── workers.py            # Worker configuration
```

### Adding a New Notification Channel

To add a new notification channel:

1. Add the new channel to `DeliveryChannel` enum in `models.py`
2. Create a new delivery method in `NotificationDeliveryService` in `tasks.py`
3. Add a new task function in `tasks.py`
4. Add routing configuration in `celery_app.py`
5. Add new API endpoints in `app.py` or `controller.py`
6. Update the worker configuration in `workers.py`

### Testing

Run tests with pytest:
```bash
pytest
```

## Deployment

### Production Considerations

1. **Security**:
   - Use environment variables for all sensitive configuration
   - Set up proper authentication for API endpoints
   - Configure TLS/SSL for all connections

2. **Scaling**:
   - Deploy multiple instances of the API server behind a load balancer
   - Run multiple worker instances for each channel
   - Configure RabbitMQ for high availability

3. **Monitoring**:
   - Set up Prometheus for collecting metrics
   - Use Grafana for visualization
   - Configure alerts for critical errors

### Docker Deployment

A `docker-compose.yml` file is provided for containerized deployment:

```yaml
version: '3'

services:
  api:
    build: .
    ports:
      - "5000:5000"
    environment:
      - DATABASE_URL=postgresql://ztp2:ztp2@db:5432/ztp2
      - CELERY_BROKER_URL=amqp://ztp2:ztp2@rabbitmq:5672//
      - CELERY_RESULT_BACKEND=db+postgresql://ztp2:ztp2@db:5432/ztp2
    depends_on:
      - db
      - rabbitmq

  push_worker:
    build: .
    command: python workers.py push
    environment:
      - DATABASE_URL=postgresql://ztp2:ztp2@db:5432/ztp2
      - CELERY_BROKER_URL=amqp://ztp2:ztp2@rabbitmq:5672//
      - CELERY_RESULT_BACKEND=db+postgresql://ztp2:ztp2@db:5432/ztp2
    depends_on:
      - db
      - rabbitmq

  email_worker:
    build: .
    command: python workers.py email
    environment:
      - DATABASE_URL=postgresql://ztp2:ztp2@db:5432/ztp2
      - CELERY_BROKER_URL=amqp://ztp2:ztp2@rabbitmq:5672//
      - CELERY_RESULT_BACKEND=db+postgresql://ztp2:ztp2@db:5432/ztp2
    depends_on:
      - db
      - rabbitmq

  flower:
    build: .
    command: celery -A celery_app.app flower --address=0.0.0.0 --port=5555
    ports:
      - "5555:5555"
    environment:
      - CELERY_BROKER_URL=amqp://ztp2:ztp2@rabbitmq:5672//
      - CELERY_RESULT_BACKEND=db+postgresql://ztp2:ztp2@db:5432/ztp2
    depends_on:
      - rabbitmq
      - db

  db:
    image: postgres:14
    environment:
      - POSTGRES_USER=ztp2
      - POSTGRES_PASSWORD=ztp2
      - POSTGRES_DB=ztp2
    volumes:
      - postgres_data:/var/lib/postgresql/data

  rabbitmq:
    image: rabbitmq:3-management
    environment:
      - RABBITMQ_DEFAULT_USER=ztp2
      - RABBITMQ_DEFAULT_PASS=ztp2
    ports:
      - "15672:15672"  # Management UI
      - "5672:5672"    # AMQP port

volumes:
  postgres_data:
```

## Troubleshooting

### Common Issues

1. **Worker not processing tasks**
   - Check RabbitMQ connection
   - Verify routing keys are correct
   - Check for errors in worker logs

2. **Database connection issues**
   - Verify PostgreSQL is running
   - Check database credentials
   - Ensure database schema is up-to-date

3. **Notification delivery failures**
   - Check external service connectivity
   - Verify recipient information is correct
   - Check for rate limiting or throttling

### Logs

Logs are crucial for troubleshooting. The system uses Python's logging module with different levels:

- ERROR: For serious issues that require immediate attention
- WARNING: For potential issues that might cause problems
- INFO: For general information about system operation
- DEBUG: For detailed debugging information

Review logs to identify issues:
```bash
# Check API server logs
tail -f api_server.log

# Check worker logs
tail -f push_worker.log
tail -f email_worker.log
```

### Support

For additional support or to report issues:
- Create an issue in the GitHub repository
- Contact the system administrator at admin@example.com

---

© 2023 Notification System. All rights reserved.
