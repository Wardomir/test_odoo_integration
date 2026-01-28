import json
from datetime import datetime
from celery.beat import Scheduler, ScheduleEntry
from celery.schedules import schedule, crontab
from redis import Redis
from app.config import get_settings

settings = get_settings()


class DatabaseScheduler(Scheduler):
    """
    Custom Celery Beat scheduler that syncs with Redis every 30 seconds.
    Supports dynamic task scheduling and deletion.
    """

    def __init__(self, *args, **kwargs):
        self.redis_client = Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True
        )
        self.schedule_key = "celery:beat:schedule"
        self.last_sync = None
        self.sync_interval = 10  # seconds
        super().__init__(*args, **kwargs)
        print(f"DatabaseScheduler initialized with sync_interval={self.sync_interval}s")

    def setup_schedule(self):
        """Load schedule from Redis on startup"""
        self.sync_schedule_from_redis()

    def sync_schedule_from_redis(self):
        """Sync schedule from Redis"""
        now = datetime.now()

        # Check if we need to sync
        if self.last_sync and (now - self.last_sync).total_seconds() < self.sync_interval:
            return

        self.logger.info("Syncing schedule from Redis...")

        try:
            # Get all scheduled tasks from Redis
            schedule_data = self.redis_client.hgetall(self.schedule_key)

            # Clear current schedule but keep entries that still exist in Redis
            current_task_names = set(self.schedule.keys())
            redis_task_names = set(schedule_data.keys())

            # Remove tasks that are no longer in Redis
            for task_name in current_task_names - redis_task_names:
                self.logger.info(f"Removing task from schedule: {task_name}")
                del self.schedule[task_name]

            # Add or update tasks from Redis
            for task_name, task_config_str in schedule_data.items():
                try:
                    task_config = json.loads(task_config_str)
                    self._add_or_update_task(task_name, task_config)
                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to parse task config for {task_name}: {e}")

            self.last_sync = now
            self.logger.info(f"Schedule synced. Active tasks: {list(self.schedule.keys())}")

        except Exception as e:
            self.logger.error(f"Failed to sync schedule from Redis: {e}")

    def _add_or_update_task(self, task_name, task_config):
        """Add or update a task in the schedule"""
        try:
            # Parse schedule configuration
            schedule_type = task_config.get("schedule_type", "interval")

            if schedule_type == "crontab":
                # Crontab schedule
                task_schedule = crontab(
                    minute=task_config.get("minute", "*"),
                    hour=task_config.get("hour", "*"),
                    day_of_week=task_config.get("day_of_week", "*"),
                    day_of_month=task_config.get("day_of_month", "*"),
                    month_of_year=task_config.get("month_of_year", "*"),
                )
            else:
                # Interval schedule (in seconds)
                interval_seconds = task_config.get("interval_seconds", 300)
                task_schedule = schedule(run_every=interval_seconds)

            # Create schedule entry
            entry = ScheduleEntry(
                name=task_name,
                task=task_config["task"],
                schedule=task_schedule,
                args=task_config.get("args", []),
                kwargs=task_config.get("kwargs", {}),
                options=task_config.get("options", {}),
            )

            self.schedule[task_name] = entry
            self.logger.info(f"Added/Updated task: {task_name}")

        except Exception as e:
            self.logger.error(f"Failed to add/update task {task_name}: {e}")

    def tick(self, *args, **kwargs):
        """Override tick to sync schedule periodically"""
        if self.last_sync:
            elapsed = (datetime.now() - self.last_sync).total_seconds()
            self.logger.debug(f"Tick called. Time since last sync: {elapsed:.1f}s")
        else:
            self.logger.debug("Tick called. No previous sync.")

        self.sync_schedule_from_redis()
        return super().tick(*args, **kwargs)

    @staticmethod
    def add_task_to_redis(task_name: str, task_config: dict):
        """
        Helper method to add a task to Redis.

        Example task_config:
        {
            "task": "app.tasks.sync_contacts",
            "schedule_type": "interval",  # or "crontab"
            "interval_seconds": 300,  # for interval type
            # For crontab type:
            # "minute": "*/5",
            # "hour": "*",
            # "day_of_week": "*",
            # "day_of_month": "*",
            # "month_of_year": "*",
            "args": [],
            "kwargs": {},
            "options": {}
        }
        """
        redis_client = Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True
        )
        schedule_key = "celery:beat:schedule"
        redis_client.hset(schedule_key, task_name, json.dumps(task_config))

    @staticmethod
    def remove_task_from_redis(task_name: str):
        """Helper method to remove a task from Redis"""
        redis_client = Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True
        )
        schedule_key = "celery:beat:schedule"
        redis_client.hdel(schedule_key, task_name)

    @staticmethod
    def get_all_tasks_from_redis():
        """Helper method to get all scheduled tasks from Redis"""
        redis_client = Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True
        )
        schedule_key = "celery:beat:schedule"
        schedule_data = redis_client.hgetall(schedule_key)

        tasks = {}
        for task_name, task_config_str in schedule_data.items():
            try:
                tasks[task_name] = json.loads(task_config_str)
            except json.JSONDecodeError:
                pass

        return tasks
