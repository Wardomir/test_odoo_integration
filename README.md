# Odoo Integration Service

A FastAPI-based microservice for synchronizing Odoo contacts and invoices with a local PostgreSQL database using Celery for scheduled background tasks.

## Architecture

This application uses a microservices architecture with the following components:

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   FastAPI   │────▶│  PostgreSQL  │     │    Redis    │
│     API     │     │   Database   │     │   (Broker)  │
└──────┬──────┘     └──────────────┘     └──────┬──────┘
       │                                         │
       │            ┌──────────────┐            │
       └───────────▶│ Celery Beat  │◀───────────┘
                    │  (Scheduler) │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │Celery Workers│
                    │  (Executor)  │
                    └──────────────┘
                           │
                    ┌──────▼───────┐
                    │  Odoo API    │
                    │   (Source)   │
                    └──────────────┘
```

## System Components

### 1. **FastAPI Application** (`odoo_fastapi`)
- RESTful API server
- Provides endpoints for managing scheduled tasks and querying synced data
- Auto-generates OpenAPI documentation at `/docs`
- Port: 8000

### 2. **PostgreSQL Database** (`odoo_postgres`)
- Stores synced contacts and invoices
- Tables: `contacts`, `invoices`
- Port: 5432

### 3. **Redis** (`odoo_redis`)
- Message broker for Celery
- Stores task schedules for Celery Beat
- Port: 6379

### 4. **Celery Beat** (`odoo_celery_beat`)
- Periodic task scheduler
- Syncs with Redis every 10 seconds to pick up new/modified schedules
- Supports dynamic task scheduling via API

### 5. **Celery Workers** (`odoo_celery_worker`)
- Executes background tasks (contact sync, invoice sync)
- Fetches data from Odoo API
- Performs database operations (insert/update/delete)

## Features

- ✅ Dynamic task scheduling with cron expressions
- ✅ Automatic sync of Odoo contacts and invoices
- ✅ RESTful API for data retrieval
- ✅ Real-time schedule management (add/remove tasks)
- ✅ Handles Odoo's session-based authentication
- ✅ Pagination support for large datasets
- ✅ Docker-compose setup for easy deployment

## Setup

### Prerequisites
- Docker & Docker Compose
- Odoo instance with API access

### Installation

1. **Clone and configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your Odoo credentials
   ```

2. **Start all services:**
   ```bash
   docker-compose up --build
   ```

3. **Access the API:**
   - API Documentation: http://localhost:8000/docs
   - API Base URL: http://localhost:8000

## API Endpoints

### Task Management

#### Schedule a Task
```http
POST /schedule-task
Content-Type: application/json

{
  "cron": "0 * * * *",
  "task_name": "sync_contacts_hourly",
  "task_path": "app.tasks.sync_contacts"
}
```

**Available Tasks:**
- `app.tasks.sync_contacts` - Sync contacts from Odoo
- `app.tasks.sync_invoices` - Sync invoices from Odoo
- `app.tasks.test_task` - Test task for verification

**Cron Examples:**
- `* * * * *` - Every minute
- `*/5 * * * *` - Every 5 minutes
- `0 * * * *` - Every hour
- `0 2 * * *` - Every day at 2 AM

#### Get All Scheduled Tasks
```http
GET /scheduled-tasks
```

Returns all currently scheduled tasks with their configuration and names.

#### Delete a Scheduled Task
```http
DELETE /scheduled-tasks/{task_name}
```

Removes a task from the schedule. Celery Beat will stop executing it within 10 seconds.

### Contacts

#### Get All Contacts
```http
GET /contacts?skip=0&limit=100
```

**Query Parameters:**
- `skip`: Number of records to skip (default: 0)
- `limit`: Maximum records to return (default: 100, max: 1000)

**Response:**
```json
[
  {
    "id": 1,
    "odoo_id": 101,
    "name": "John Doe",
    "email": "john.doe@example.com",
    "phone": "+1234567890",
    "write_date": "2026-01-28T10:00:00",
    "created_at": "2026-01-28T09:00:00",
    "updated_at": "2026-01-28T10:00:00"
  }
]
```

#### Get Contact by ID
```http
GET /contacts/{contact_id}
```

Returns a single contact by database ID.

### Invoices

#### Get All Invoices
```http
GET /invoices?skip=0&limit=100
```

**Query Parameters:**
- `skip`: Number of records to skip (default: 0)
- `limit`: Maximum records to return (default: 100, max: 1000)

**Response:**
```json
[
  {
    "id": 1,
    "odoo_id": 501,
    "name": "INV/2026/0001",
    "move_type": "out_invoice",
    "invoice_date": "2026-01-28T00:00:00",
    "partner_id": 101,
    "partner_name": "John Doe",
    "amount_total": 1500.00,
    "amount_residual": 0.00,
    "state": "posted",
    "currency_id": 1,
    "currency_name": "USD",
    "write_date": "2026-01-28T10:00:00",
    "create_date": "2026-01-28T09:00:00",
    "created_at": "2026-01-28T10:30:00",
    "updated_at": "2026-01-28T10:30:00"
  }
]
```

#### Get Invoice by ID
```http
GET /invoices/{invoice_id}
```

Returns a single invoice by database ID.

### Health Check
```http
GET /health
```

Returns system health status and configuration info.

## Usage Examples

### Schedule Contact Sync (Every 30 Minutes)
```bash
curl -X POST http://localhost:8000/schedule-task \
  -H "Content-Type: application/json" \
  -d '{
    "cron": "*/30 * * * *",
    "task_name": "sync_contacts_every_30min",
    "task_path": "app.tasks.sync_contacts"
  }'
```

### Schedule Invoice Sync (Daily at 2 AM)
```bash
curl -X POST http://localhost:8000/schedule-task \
  -H "Content-Type: application/json" \
  -d '{
    "cron": "0 2 * * *",
    "task_name": "sync_invoices_daily",
    "task_path": "app.tasks.sync_invoices"
  }'
```

### Get All Scheduled Tasks
```bash
curl http://localhost:8000/scheduled-tasks
```

### Remove a Scheduled Task
```bash
curl -X DELETE http://localhost:8000/scheduled-tasks/sync_contacts_every_30min
```

### Query Contacts
```bash
curl http://localhost:8000/contacts?limit=10
```

### Query Invoices
```bash
curl http://localhost:8000/invoices?limit=10
```

## Database Schema

### Contacts Table
- `id` - Primary key
- `odoo_id` - Odoo contact ID (unique)
- `name` - Contact name
- `email` - Email address
- `phone` - Phone number
- `write_date` - Last modified in Odoo
- `created_at` - Created in local DB
- `updated_at` - Updated in local DB

### Invoices Table
- `id` - Primary key
- `odoo_id` - Odoo invoice ID (unique)
- `name` - Invoice number
- `move_type` - Invoice type (e.g., "out_invoice")
- `invoice_date` - Invoice date
- `partner_id` - Partner's Odoo ID
- `partner_name` - Partner name
- `amount_total` - Total amount
- `amount_residual` - Residual amount
- `state` - Invoice state (draft, posted, etc.)
- `currency_id` - Currency Odoo ID
- `currency_name` - Currency name
- `write_date` - Last modified in Odoo
- `create_date` - Created in Odoo
- `created_at` - Created in local DB
- `updated_at` - Updated in local DB

## Development

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f odoo_celery_worker
docker-compose logs -f odoo_celery_beat
docker-compose logs -f odoo_fastapi
```

### Restart a Service
```bash
docker-compose restart odoo_celery_worker
```

### Stop All Services
```bash
docker-compose down
```

### Stop and Remove Volumes
```bash
docker-compose down -v
```

## How It Works

1. **Task Scheduling**: Users schedule tasks via the `/schedule-task` endpoint, which stores task configuration in Redis.

2. **Schedule Sync**: Celery Beat syncs with Redis every 10 seconds to pick up new or modified task schedules.

3. **Task Execution**: When a task's scheduled time arrives, Celery Beat sends it to the Redis queue.

4. **Worker Processing**: Celery Workers pick up tasks from the queue and execute them:
   - Authenticate with Odoo (session-based)
   - Fetch data from Odoo API
   - Compare with local database
   - Insert new records, update existing ones, delete removed ones

5. **Data Access**: Users query synced data through REST API endpoints with pagination support.

## Configuration

Key environment variables in `.env`:

```bash
# PostgreSQL
POSTGRES_USER=odoo_user
POSTGRES_PASSWORD=odoo_password
POSTGRES_DB=odoo_integration
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

# Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Odoo (Update with your credentials)
ODOO_URL=https://your-odoo-instance.com
ODOO_DB=your_database_name
ODOO_USERNAME=your_username
ODOO_PASSWORD=your_password
```

## Troubleshooting

### Celery Beat not picking up tasks
- Check Redis connection: `docker-compose logs odoo_redis`
- Verify task is in Redis: `GET /scheduled-tasks`
- Wait up to 10 seconds for sync interval

### Tasks failing to execute
- Check worker logs: `docker-compose logs odoo_celery_worker`
- Verify Odoo credentials in `.env`
- Test Odoo connectivity

### Database connection errors
- Ensure PostgreSQL is healthy: `docker-compose ps`
- Check database credentials in `.env`

## License

MIT
