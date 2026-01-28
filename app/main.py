from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional
from app.config import get_settings
from app.scheduler import DatabaseScheduler
from app.database import get_db, Base, engine
from app.models import Contact, Invoice
from app.auth import verify_api_key

settings = get_settings()

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Odoo Integration API",
    description="API for syncing Odoo contacts and invoices",
    version="1.0.0"
)


class ScheduleTaskRequest(BaseModel):
    cron: str
    task_name: str
    task_path: str


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "database": settings.database_url.split("@")[1],  # Hide credentials
        "redis": settings.redis_url
    }


@app.post("/schedule-task", dependencies=[Depends(verify_api_key)])
async def schedule_task(request: ScheduleTaskRequest):
    """
    Schedule a task using a cron string.

    Parameters:
    - cron: Cron expression (e.g., "*/5 * * * *" for every 5 minutes)
    - task_name: Unique name for this scheduled task (e.g., "sync_contacts_daily")
    - task_path: Full path to the Celery task (e.g., "app.tasks.sync_contacts")

    Example cron strings:
    - "* * * * *" - Every minute
    - "*/5 * * * *" - Every 5 minutes
    - "0 * * * *" - Every hour
    - "0 0 * * *" - Every day at midnight
    - "*/30 * * * *" - Every 30 minutes

    Available tasks:
    - app.tasks.sync_contacts
    - app.tasks.sync_invoices
    - app.tasks.test_task
    """
    try:
        # Parse cron string (minute hour day_of_month month_of_year day_of_week)
        cron_parts = request.cron.split()

        if len(cron_parts) != 5:
            raise HTTPException(
                status_code=400,
                detail="Invalid cron format. Expected 5 parts: minute hour day_of_month month_of_year day_of_week"
            )

        minute, hour, day_of_month, month_of_year, day_of_week = cron_parts

        # Create task configuration
        task_config = {
            "task": request.task_path,
            "schedule_type": "crontab",
            "minute": minute,
            "hour": hour,
            "day_of_week": day_of_week,
            "day_of_month": day_of_month,
            "month_of_year": month_of_year,
            "args": [],
            "kwargs": {},
            "options": {}
        }

        # Add task to Redis
        DatabaseScheduler.add_task_to_redis(request.task_name, task_config)

        return {
            "status": "success",
            "message": f"Task '{request.task_path}' scheduled with cron: {request.cron}",
            "task_name": request.task_name,
            "note": "Celery Beat will pick up this task within 10 seconds"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/scheduled-tasks", dependencies=[Depends(verify_api_key)])
async def get_scheduled_tasks():
    """
    Get all currently scheduled tasks from Redis.
    Returns task name along with configuration.
    """
    try:
        tasks = DatabaseScheduler.get_all_tasks_from_redis()

        # Transform tasks to include the task name in each task object
        tasks_with_names = {
            task_name: {**task_config, "task_name": task_name}
            for task_name, task_config in tasks.items()
        }

        return {
            "status": "success",
            "count": len(tasks_with_names),
            "tasks": tasks_with_names
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/scheduled-tasks/{task_name}", dependencies=[Depends(verify_api_key)])
async def delete_scheduled_task(task_name: str):
    """
    Delete a scheduled task from Redis.
    """
    try:
        # Check if task exists
        tasks = DatabaseScheduler.get_all_tasks_from_redis()
        if task_name not in tasks:
            raise HTTPException(
                status_code=404,
                detail=f"Task '{task_name}' not found"
            )

        # Remove task from Redis
        DatabaseScheduler.remove_task_from_redis(task_name)

        return {
            "status": "success",
            "message": f"Task '{task_name}' has been deleted",
            "note": "Celery Beat will remove this task from its schedule within 30 seconds"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Pydantic schemas for contacts
class ContactResponse(BaseModel):
    id: int
    odoo_id: int
    name: str
    email: Optional[str]
    phone: Optional[str]
    write_date: Optional[str]
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


@app.get("/contacts", response_model=List[ContactResponse], dependencies=[Depends(verify_api_key)])
async def get_contacts(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Get all contacts from the database.

    Parameters:
    - skip: Number of records to skip (for pagination)
    - limit: Maximum number of records to return (max 1000)
    """
    if limit > 1000:
        limit = 1000

    contacts = db.query(Contact).offset(skip).limit(limit).all()
    return contacts


@app.get("/contacts/{contact_id}", response_model=ContactResponse, dependencies=[Depends(verify_api_key)])
async def get_contact_by_id(
    contact_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a single contact by ID.
    """
    contact = db.query(Contact).filter(Contact.id == contact_id).first()

    if not contact:
        raise HTTPException(status_code=404, detail=f"Contact with id {contact_id} not found")

    return contact


# Pydantic schemas for invoices
class InvoiceResponse(BaseModel):
    id: int
    odoo_id: int
    name: str
    move_type: str
    invoice_date: Optional[str]
    partner_id: Optional[int]
    partner_name: Optional[str]
    amount_total: Optional[float]
    amount_residual: Optional[float]
    state: Optional[str]
    currency_id: Optional[int]
    currency_name: Optional[str]
    write_date: Optional[str]
    create_date: Optional[str]
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


@app.get("/invoices", response_model=List[InvoiceResponse], dependencies=[Depends(verify_api_key)])
async def get_invoices(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Get all invoices from the database.

    Parameters:
    - skip: Number of records to skip (for pagination)
    - limit: Maximum number of records to return (max 1000)
    """
    if limit > 1000:
        limit = 1000

    invoices = db.query(Invoice).offset(skip).limit(limit).all()
    return invoices


@app.get("/invoices/{invoice_id}", response_model=InvoiceResponse, dependencies=[Depends(verify_api_key)])
async def get_invoice_by_id(
    invoice_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a single invoice by ID.
    """
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()

    if not invoice:
        raise HTTPException(status_code=404, detail=f"Invoice with id {invoice_id} not found")

    return invoice
