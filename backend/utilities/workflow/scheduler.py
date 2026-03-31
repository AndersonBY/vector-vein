from __future__ import annotations

import threading
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Iterable, TypedDict
from zoneinfo import ZoneInfo

from api.utils import run_workflow_common
from models import Workflow, WorkflowRunRecord, WorkflowRunSchedule, database
from utilities.general import mprint_with_name


mprint = mprint_with_name(name="Workflow Scheduler")

MONTH_NAME_MAP = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

DOW_NAME_MAP = {
    "sun": 0,
    "mon": 1,
    "tue": 2,
    "wed": 3,
    "thu": 4,
    "fri": 5,
    "sat": 6,
}

CRON_FIELD_SPECS = (
    ("minute", 0, 59, None),
    ("hour", 0, 23, None),
    ("day_of_month", 1, 31, None),
    ("month", 1, 12, MONTH_NAME_MAP),
    ("day_of_week", 0, 7, DOW_NAME_MAP),
)


class ParsedCronExpression(TypedDict):
    minute: set[int]
    hour: set[int]
    day_of_month: set[int]
    month: set[int]
    day_of_week: set[int]
    minute_is_any: bool
    hour_is_any: bool
    day_of_month_is_any: bool
    month_is_any: bool
    day_of_week_is_any: bool


def _safe_timezone(timezone_name: str | None) -> ZoneInfo:
    if not timezone_name:
        return ZoneInfo("Asia/Shanghai")
    try:
        return ZoneInfo(timezone_name)
    except Exception:
        return ZoneInfo("Asia/Shanghai")


def _parse_field_value(value: str, minimum: int, maximum: int, alias_map: dict[str, int] | None) -> int:
    normalized = value.strip().lower()
    if alias_map and normalized in alias_map:
        parsed = alias_map[normalized]
    else:
        parsed = int(normalized)
    if not minimum <= parsed <= maximum:
        raise ValueError(f"cron value out of range: {value}")
    return parsed


def _expand_cron_part(
    part: str,
    minimum: int,
    maximum: int,
    alias_map: dict[str, int] | None = None,
) -> set[int]:
    values: set[int] = set()
    for raw_chunk in part.split(","):
        chunk = raw_chunk.strip()
        if not chunk:
            raise ValueError("empty cron chunk")

        if "/" in chunk:
            base, step_text = chunk.split("/", 1)
            step = int(step_text)
            if step <= 0:
                raise ValueError("cron step must be positive")
        else:
            base = chunk
            step = 1

        if base == "*":
            start = minimum
            end = maximum
        elif "-" in base:
            start_text, end_text = base.split("-", 1)
            start = _parse_field_value(start_text, minimum, maximum, alias_map)
            end = _parse_field_value(end_text, minimum, maximum, alias_map)
            if end < start:
                raise ValueError("cron range end must be greater than start")
        else:
            start = end = _parse_field_value(base, minimum, maximum, alias_map)

        for value in range(start, end + 1, step):
            normalized_value = 0 if maximum == 7 and value == 7 else value
            values.add(normalized_value)
    return values


def validate_cron_expression(cron_expression: str) -> bool:
    try:
        parse_cron_expression(cron_expression)
        return True
    except Exception:
        return False


def parse_cron_expression(cron_expression: str) -> ParsedCronExpression:
    fields = cron_expression.strip().split()
    if len(fields) != 5:
        raise ValueError("cron expression must contain 5 fields")

    minute_text, hour_text, day_of_month_text, month_text, day_of_week_text = fields

    return {
        "minute": _expand_cron_part(minute_text, 0, 59, None),
        "hour": _expand_cron_part(hour_text, 0, 23, None),
        "day_of_month": _expand_cron_part(day_of_month_text, 1, 31, None),
        "month": _expand_cron_part(month_text, 1, 12, MONTH_NAME_MAP),
        "day_of_week": _expand_cron_part(day_of_week_text, 0, 7, DOW_NAME_MAP),
        "minute_is_any": minute_text.strip() == "*",
        "hour_is_any": hour_text.strip() == "*",
        "day_of_month_is_any": day_of_month_text.strip() == "*",
        "month_is_any": month_text.strip() == "*",
        "day_of_week_is_any": day_of_week_text.strip() == "*",
    }


def cron_matches_datetime(cron_expression: str, current_time: datetime) -> bool:
    parsed = parse_cron_expression(cron_expression)

    minute_match = current_time.minute in parsed["minute"]
    hour_match = current_time.hour in parsed["hour"]
    month_match = current_time.month in parsed["month"]
    dom_match = current_time.day in parsed["day_of_month"]
    cron_weekday = (current_time.weekday() + 1) % 7
    dow_match = cron_weekday in parsed["day_of_week"]

    dom_any = bool(parsed["day_of_month_is_any"])
    dow_any = bool(parsed["day_of_week_is_any"])
    if dom_any and dow_any:
        day_match = True
    elif dom_any:
        day_match = dow_match
    elif dow_any:
        day_match = dom_match
    else:
        day_match = dom_match or dow_match

    return minute_match and hour_match and month_match and day_match


def get_next_run_time(
    cron_expression: str,
    timezone_name: str | None,
    from_time: datetime | None = None,
    max_minutes: int = 60 * 24 * 365,
) -> datetime | None:
    timezone_info = _safe_timezone(timezone_name)
    cursor = (from_time or datetime.now(timezone.utc)).astimezone(timezone_info)
    cursor = cursor.replace(second=0, microsecond=0) + timedelta(minutes=1)

    for _ in range(max_minutes):
        if cron_matches_datetime(cron_expression, cursor):
            return cursor
        cursor += timedelta(minutes=1)
    return None


class WorkflowScheduler:
    def __init__(self, poll_interval_seconds: int = 15):
        self.poll_interval_seconds = poll_interval_seconds
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._last_triggered: dict[str, str] = {}
        self._lock = threading.Lock()

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="workflow-scheduler")
        self._thread.start()
        mprint("Workflow scheduler started")

    def stop(self):
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._thread = None
        mprint("Workflow scheduler stopped")

    def _run_loop(self):
        while not self._stop_event.is_set():
            try:
                self.tick()
            except Exception as error:
                mprint.error(f"scheduler tick failed: {error}")
            self._stop_event.wait(self.poll_interval_seconds)

    def tick(self, now_utc: datetime | None = None):
        current_utc = now_utc or datetime.now(timezone.utc)
        with database.connection_context():
            schedules: Iterable[WorkflowRunSchedule] = (
                WorkflowRunSchedule.select(WorkflowRunSchedule, Workflow)
                .join(Workflow)
                .where(
                    WorkflowRunSchedule.status == "VALID",
                    Workflow.status == "VALID",
                )
            )

            for schedule in schedules:
                self._try_run_schedule(schedule, current_utc)

    def _try_run_schedule(self, schedule: WorkflowRunSchedule, current_utc: datetime):
        cron_expression = schedule.cron_expression.strip() if isinstance(schedule.cron_expression, str) else ""
        if not cron_expression or not validate_cron_expression(cron_expression):
            return

        schedule_data = schedule.data if isinstance(schedule.data, dict) else {}
        timezone_name = str(schedule_data.get("timezone") or "Asia/Shanghai")
        timezone_info = _safe_timezone(timezone_name)
        local_time = current_utc.astimezone(timezone_info).replace(second=0, microsecond=0)
        minute_key = local_time.strftime("%Y-%m-%dT%H:%M%z")
        schedule_key = schedule.sid.hex
        workflow_obj = schedule.workflow
        if workflow_obj is None:
            return

        with self._lock:
            if self._last_triggered.get(schedule_key) == minute_key:
                return

        if not cron_matches_datetime(cron_expression, local_time):
            return

        latest_record = (
            WorkflowRunRecord.select()
            .where(
                WorkflowRunRecord.workflow == workflow_obj,
                WorkflowRunRecord.run_from == WorkflowRunRecord.RunFromTypes.SCHEDULE,
            )
            .order_by(WorkflowRunRecord.start_time.desc())
            .first()
        )
        if latest_record and latest_record.start_time:
            latest_local_minute = latest_record.start_time.astimezone(timezone_info).replace(second=0, microsecond=0)
            if latest_local_minute == local_time:
                with self._lock:
                    self._last_triggered[schedule_key] = minute_key
                return

        workflow_payload = deepcopy(workflow_obj.data if isinstance(workflow_obj.data, dict) else {})
        run_workflow_common(
            workflow_data=workflow_payload,
            workflow=workflow_obj,
            run_from=WorkflowRunRecord.RunFromTypes.SCHEDULE,
            workflow_version=workflow_obj.version,
        )

        schedule.schedule_time = local_time
        schedule.update_time = datetime.now()
        schedule.save()

        with self._lock:
            self._last_triggered[schedule_key] = minute_key


workflow_scheduler = WorkflowScheduler()
