from __future__ import annotations

from datetime import timedelta

DOMAIN = "homequests"
NAME = "HomeQuests"
VERSION = "0.1.10"
ISSUE_URL = "https://github.com/kolossboss/homequests-backend-ha/issues"

CONF_BASE_URL = "base_url"
CONF_ENTRY_ID = "entry_id"
CONF_FAMILY_ID = "family_id"
CONF_FAMILY_NAME = "family_name"
CONF_PASSWORD = "password"
CONF_USERNAME = "username"
CONF_USER_ID = "user_id"
CONF_USER_NAME = "user_name"

DEFAULT_SCAN_INTERVAL = timedelta(minutes=2)
DEFAULT_REMINDER_WINDOW_MINUTES = 1440
REQUEST_TIMEOUT = 20
LIVE_RECONNECT_SECONDS = 10
LIVE_REFRESH_COOLDOWN_SECONDS = 3

ATTR_DEVICE_ID = "device_id"
ATTR_FAMILY_ID = "family_id"
ATTR_FAMILY_NAME = "family_name"
ATTR_MEMBER_NAME = "member_name"
ATTR_MEMBER_USER_ID = "member_user_id"
ATTR_TYPE = "type"

EVENT_HOMEQUESTS = "homequests_event"
EVENT_NEW_AVAILABLE_TASKS = "new_available_tasks"
EVENT_TASKS_SUBMITTED = "tasks_submitted"
EVENT_REWARD_REQUESTS_PENDING = "reward_requests_pending"
EVENT_SPECIAL_TASKS_AVAILABLE = "special_tasks_available"
HOMEQUESTS_EVENT_TYPES = (
    EVENT_NEW_AVAILABLE_TASKS,
    EVENT_TASKS_SUBMITTED,
    EVENT_REWARD_REQUESTS_PENDING,
    EVENT_SPECIAL_TASKS_AVAILABLE,
)

SERVICE_ADJUST_POINTS = "adjust_points"
SERVICE_REFRESH = "refresh"
SERVICE_REPORT_TASK_MISSED = "report_task_missed"
SERVICE_REVIEW_MISSED_TASK = "review_missed_task"
SERVICE_REVIEW_REDEMPTION = "review_redemption"
SERVICE_REVIEW_TASK = "review_task"
SERVICE_SUBMIT_TASK = "submit_task"

TASK_STATUS_OPEN = "open"
TASK_STATUS_SUBMITTED = "submitted"
TASK_STATUS_MISSED_SUBMITTED = "missed_submitted"
TASK_STATUS_APPROVED = "approved"
TASK_STATUS_REJECTED = "rejected"

ROLE_CHILD = "child"

PLATFORMS = ["sensor", "binary_sensor", "button", "event", "todo", "calendar"]

REDACT_KEYS = {
    "access_token",
    "authorization",
    "comment",
    "description",
    "device_id",
    "display_name",
    "email",
    "message",
    "note",
    "password",
    "title",
    "user_name",
}
