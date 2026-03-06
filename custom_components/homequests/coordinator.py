from __future__ import annotations

import asyncio
from collections import defaultdict
from contextlib import suppress
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import HomeQuestsApiError, HomeQuestsAuthError, HomeQuestsClient, HomeQuestsConnectionError, parse_sse_payload
from .const import (
    ATTR_DEVICE_ID,
    ATTR_FAMILY_ID,
    ATTR_FAMILY_NAME,
    ATTR_MEMBER_NAME,
    ATTR_MEMBER_USER_ID,
    ATTR_TYPE,
    CONF_ENTRY_ID,
    CONF_FAMILY_ID,
    CONF_FAMILY_NAME,
    DEFAULT_REMINDER_WINDOW_MINUTES,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVENT_HOMEQUESTS,
    EVENT_NEW_AVAILABLE_TASKS,
    EVENT_REWARD_REQUESTS_PENDING,
    EVENT_SPECIAL_TASKS_AVAILABLE,
    EVENT_TASKS_SUBMITTED,
    LIVE_RECONNECT_SECONDS,
    LIVE_REFRESH_COOLDOWN_SECONDS,
    ROLE_CHILD,
    TASK_STATUS_APPROVED,
    TASK_STATUS_MISSED_SUBMITTED,
    TASK_STATUS_OPEN,
    TASK_STATUS_REJECTED,
    TASK_STATUS_SUBMITTED,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class HomeQuestsRuntimeData:
    api: HomeQuestsClient
    coordinator: "HomeQuestsDataUpdateCoordinator"


class HomeQuestsDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: HomeQuestsClient,
    ) -> None:
        self.entry = entry
        self.api = api
        self.family_id = int(entry.data[CONF_FAMILY_ID])
        self.family_name = str(entry.data[CONF_FAMILY_NAME])
        self._live_listener_task: asyncio.Task | None = None
        self._live_stop_event = asyncio.Event()
        self._last_live_event_id = 0
        self._last_live_refresh_ts = 0.0
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{self.family_id}",
            update_interval=DEFAULT_SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            raw_snapshot = await self.api.async_get_dashboard_snapshot(
                self.family_id,
                reminder_window_minutes=DEFAULT_REMINDER_WINDOW_MINUTES,
            )
        except HomeQuestsAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except HomeQuestsConnectionError as err:
            raise UpdateFailed(str(err)) from err
        except HomeQuestsApiError as err:
            raise UpdateFailed(str(err)) from err

        processed = _build_processed_snapshot(
            family_id=self.family_id,
            family_name=self.family_name,
            raw_snapshot=raw_snapshot,
        )
        if self.data is not None:
            self._emit_automation_events(previous=self.data, current=processed)
        return processed

    async def async_manual_refresh(self) -> None:
        await self.async_request_refresh()

    async def async_start_live_listener(self) -> None:
        if self._live_listener_task is not None and not self._live_listener_task.done():
            return
        self._live_stop_event.clear()
        self._live_listener_task = self.hass.async_create_task(
            self._async_live_listener_loop(),
            name=f"{DOMAIN}_live_listener_{self.family_id}",
        )

    async def async_stop_live_listener(self) -> None:
        self._live_stop_event.set()
        if self._live_listener_task is None:
            return
        self._live_listener_task.cancel()
        with suppress(asyncio.CancelledError):
            await self._live_listener_task
        self._live_listener_task = None

    async def _async_live_listener_loop(self) -> None:
        while not self._live_stop_event.is_set():
            try:
                response = await self.api.async_open_live_stream(
                    self.family_id,
                    since_id=self._last_live_event_id,
                )
                async with response:
                    await self._async_consume_live_stream(response)
            except HomeQuestsAuthError:
                _LOGGER.warning("HomeQuests live stream auth error; fallback to polling until reauth succeeds")
            except HomeQuestsConnectionError as err:
                _LOGGER.debug("HomeQuests live stream connection error: %s", err)
            except HomeQuestsApiError as err:
                _LOGGER.debug("HomeQuests live stream API error: %s", err)
            except asyncio.CancelledError:
                raise
            except Exception as err:  # pragma: no cover - defensive
                _LOGGER.exception("Unexpected error in HomeQuests live stream: %s", err)

            if self._live_stop_event.is_set():
                break
            try:
                await asyncio.wait_for(self._live_stop_event.wait(), timeout=LIVE_RECONNECT_SECONDS)
            except asyncio.TimeoutError:
                continue

    async def _async_consume_live_stream(self, response: Any) -> None:
        event_name = ""
        data_lines: list[str] = []
        event_id: int | None = None

        async for raw in response.content:
            if self._live_stop_event.is_set():
                return

            line = raw.decode("utf-8", errors="ignore").rstrip("\r\n")
            if not line:
                await self._async_handle_live_event(
                    event_name=event_name,
                    event_id=event_id,
                    raw_data="\n".join(data_lines),
                )
                event_name = ""
                data_lines = []
                event_id = None
                continue

            if line.startswith(":"):
                continue
            if line.startswith("id:"):
                try:
                    event_id = int(line[3:].strip())
                except ValueError:
                    event_id = None
                continue
            if line.startswith("event:"):
                event_name = line[6:].strip()
                continue
            if line.startswith("data:"):
                data_lines.append(line[5:].lstrip())

        if event_name or data_lines or event_id is not None:
            await self._async_handle_live_event(
                event_name=event_name,
                event_id=event_id,
                raw_data="\n".join(data_lines),
            )

    async def _async_handle_live_event(self, *, event_name: str, event_id: int | None, raw_data: str) -> None:
        if event_id is not None:
            self._last_live_event_id = max(self._last_live_event_id, event_id)
        if event_name not in {"family_update", "notification.test"}:
            return

        payload = parse_sse_payload(raw_data)
        if payload:
            event_obj = payload.get("id")
            if isinstance(event_obj, int):
                self._last_live_event_id = max(self._last_live_event_id, event_obj)

        now_ts = time.monotonic()
        if now_ts - self._last_live_refresh_ts < LIVE_REFRESH_COOLDOWN_SECONDS:
            return
        self._last_live_refresh_ts = now_ts
        self.hass.async_create_task(self.async_request_refresh())

    def _emit_automation_events(self, *, previous: dict[str, Any], current: dict[str, Any]) -> None:
        self._emit_family_event_increase(
            previous=previous,
            current=current,
            stat_key="tasks_pending_review_total",
            event_type=EVENT_TASKS_SUBMITTED,
            id_key="pending_review_task_ids",
            title_key="pending_review_task_titles",
        )
        self._emit_family_event_increase(
            previous=previous,
            current=current,
            stat_key="pending_reward_redemptions_total",
            event_type=EVENT_REWARD_REQUESTS_PENDING,
            id_key="pending_redemption_ids",
            title_key="pending_redemption_labels",
        )

        previous_children = previous.get("children", {})
        current_children = current.get("children", {})
        for user_id, child_state in current_children.items():
            previous_child_state = previous_children.get(user_id)
            if previous_child_state is None:
                continue
            self._emit_member_event_increase(
                previous=previous_child_state,
                current=child_state,
                event_type=EVENT_NEW_AVAILABLE_TASKS,
                stat_key="available_tasks",
                id_key="available_task_ids",
                title_key="available_task_titles",
            )
            self._emit_member_event_increase(
                previous=previous_child_state,
                current=child_state,
                event_type=EVENT_SPECIAL_TASKS_AVAILABLE,
                stat_key="available_special_tasks",
                id_key="available_special_task_template_ids",
                title_key="available_special_task_titles",
            )
            self._emit_member_event_increase(
                previous=previous_child_state,
                current=child_state,
                event_type=EVENT_TASKS_SUBMITTED,
                stat_key="pending_reviews",
                id_key="pending_review_task_ids",
                title_key="pending_review_task_titles",
            )

    def _emit_family_event_increase(
        self,
        *,
        previous: dict[str, Any],
        current: dict[str, Any],
        event_type: str,
        stat_key: str,
        id_key: str,
        title_key: str,
    ) -> None:
        old_value = int(previous.get("summary", {}).get(stat_key, 0))
        new_value = int(current.get("summary", {}).get(stat_key, 0))
        if new_value <= old_value:
            return

        new_ids = list(current.get("summary", {}).get(id_key, []))
        old_ids = set(previous.get("summary", {}).get(id_key, []))
        delta_ids = [value for value in new_ids if value not in old_ids]
        payload = {
            ATTR_TYPE: event_type,
            CONF_ENTRY_ID: self.entry.entry_id,
            ATTR_FAMILY_ID: self.family_id,
            ATTR_FAMILY_NAME: self.family_name,
            "old_count": old_value,
            "new_count": new_value,
            "delta_count": new_value - old_value,
            "item_ids": delta_ids,
            "items": [
                title
                for item_id, title in zip(current.get("summary", {}).get(id_key, []), current.get("summary", {}).get(title_key, []), strict=False)
                if item_id in delta_ids
            ],
            ATTR_DEVICE_ID: self._lookup_family_device_id(),
        }
        self.hass.bus.async_fire(EVENT_HOMEQUESTS, payload)

    def _emit_member_event_increase(
        self,
        *,
        previous: dict[str, Any],
        current: dict[str, Any],
        event_type: str,
        stat_key: str,
        id_key: str,
        title_key: str,
    ) -> None:
        old_value = int(previous.get(stat_key, 0))
        new_value = int(current.get(stat_key, 0))
        if new_value <= old_value:
            return

        new_ids = list(current.get(id_key, []))
        old_ids = set(previous.get(id_key, []))
        delta_ids = [value for value in new_ids if value not in old_ids]
        payload = {
            ATTR_TYPE: event_type,
            CONF_ENTRY_ID: self.entry.entry_id,
            ATTR_FAMILY_ID: self.family_id,
            ATTR_FAMILY_NAME: self.family_name,
            ATTR_MEMBER_USER_ID: current["user_id"],
            ATTR_MEMBER_NAME: current["display_name"],
            "old_count": old_value,
            "new_count": new_value,
            "delta_count": new_value - old_value,
            "item_ids": delta_ids,
            "items": [
                title
                for item_id, title in zip(current.get(id_key, []), current.get(title_key, []), strict=False)
                if item_id in delta_ids
            ],
            ATTR_DEVICE_ID: self._lookup_member_device_id(current["user_id"]),
        }
        self.hass.bus.async_fire(EVENT_HOMEQUESTS, payload)

    def _lookup_family_device_id(self) -> str | None:
        registry = dr.async_get(self.hass)
        device = registry.async_get_device(identifiers={(DOMAIN, family_device_identifier(self.family_id))})
        return device.id if device else None

    def _lookup_member_device_id(self, user_id: int) -> str | None:
        registry = dr.async_get(self.hass)
        device = registry.async_get_device(identifiers={(DOMAIN, member_device_identifier(self.family_id, user_id))})
        return device.id if device else None


def family_device_identifier(family_id: int) -> str:
    return f"family_{family_id}"


def member_device_identifier(family_id: int, user_id: int) -> str:
    return f"family_{family_id}_member_{user_id}"


def family_device_info(family_id: int, family_name: str) -> dict[str, Any]:
    return {
        "identifiers": {(DOMAIN, family_device_identifier(family_id))},
        "name": f"HomeQuests {family_name}",
        "manufacturer": "kolossboss",
        "model": "HomeQuests Family",
        "entry_type": dr.DeviceEntryType.SERVICE,
    }


def member_device_info(family_id: int, family_name: str, user_id: int, member_name: str) -> dict[str, Any]:
    return {
        "identifiers": {(DOMAIN, member_device_identifier(family_id, user_id))},
        "name": member_name,
        "manufacturer": "kolossboss",
        "model": "HomeQuests Member",
        "via_device": (DOMAIN, family_device_identifier(family_id)),
        "suggested_area": family_name,
    }


def _build_processed_snapshot(
    *,
    family_id: int,
    family_name: str,
    raw_snapshot: dict[str, Any],
) -> dict[str, Any]:
    now = dt_util.now()
    tomorrow_start = dt_util.start_of_local_day(now + timedelta(days=1))

    members = deepcopy(raw_snapshot.get("members", []))
    tasks = deepcopy(raw_snapshot.get("tasks", []))
    templates = deepcopy(raw_snapshot.get("special_task_templates", []))
    rewards = deepcopy(raw_snapshot.get("rewards", []))
    redemptions = deepcopy(raw_snapshot.get("redemptions", []))
    balances = deepcopy(raw_snapshot.get("points_balances", []))
    reminders = deepcopy(raw_snapshot.get("upcoming_reminders", []))
    me = deepcopy(raw_snapshot.get("me", {}))

    for item in tasks:
        item["due_at_ts"] = _parse_backend_datetime(item.get("due_at"))
        item["created_at_ts"] = _parse_backend_datetime(item.get("created_at"))
        item["updated_at_ts"] = _parse_backend_datetime(item.get("updated_at"))
    for item in redemptions:
        item["requested_at_ts"] = _parse_backend_datetime(item.get("requested_at"))
        item["reviewed_at_ts"] = _parse_backend_datetime(item.get("reviewed_at"))

    balances_by_user = {int(item["user_id"]): int(item.get("balance", 0)) for item in balances}
    members_by_user = {int(item["user_id"]): item for item in members}
    children = {
        int(member["user_id"]): member
        for member in members
        if member.get("role") == ROLE_CHILD
    }

    visible_tasks = [task for task in tasks if task.get("is_active", True) is not False or task.get("status") == TASK_STATUS_APPROVED]

    pending_redemptions = [entry for entry in redemptions if entry.get("status") == "pending"]
    member_special_availability = _build_special_task_availability(templates, tasks, children.keys(), now)
    member_children_data = {
        user_id: _build_child_stats(
            member=member,
            tasks=tasks,
            balances_by_user=balances_by_user,
            redemptions=redemptions,
            available_special_tasks=member_special_availability.get(user_id, []),
            now=now,
            tomorrow_start=tomorrow_start,
        )
        for user_id, member in children.items()
    }

    pending_review_tasks = [
        task
        for task in visible_tasks
        if task.get("status") in {TASK_STATUS_SUBMITTED, TASK_STATUS_MISSED_SUBMITTED}
    ]
    overdue_visible_tasks = [
        task
        for child in member_children_data.values()
        for task in child["overdue_task_objects"]
    ]
    actionable_visible_tasks = [
        task
        for child in member_children_data.values()
        for task in child["available_task_objects"]
    ]

    summary = {
        "tasks_total": len(visible_tasks),
        "special_task_templates_total": len(templates),
        "special_task_templates_active": sum(1 for item in templates if item.get("is_active", True)),
        "tasks_open_total": sum(1 for task in visible_tasks if task.get("status") == TASK_STATUS_OPEN),
        "tasks_rejected_total": sum(1 for task in visible_tasks if task.get("status") == TASK_STATUS_REJECTED),
        "tasks_completed_total": sum(1 for task in visible_tasks if task.get("status") == TASK_STATUS_APPROVED),
        "tasks_overdue_total": len(overdue_visible_tasks),
        "tasks_submitted_total": sum(1 for task in visible_tasks if task.get("status") == TASK_STATUS_SUBMITTED),
        "tasks_missed_submitted_total": sum(1 for task in visible_tasks if task.get("status") == TASK_STATUS_MISSED_SUBMITTED),
        "tasks_pending_review_total": len(pending_review_tasks),
        "tasks_actionable_total": len(actionable_visible_tasks),
        "rewards_total": len(rewards),
        "rewards_active_total": sum(1 for item in rewards if item.get("is_active", True)),
        "pending_reward_redemptions_total": len(pending_redemptions),
        "upcoming_task_reminders_total": len(reminders),
        "pending_review_task_ids": [int(task["id"]) for task in pending_review_tasks],
        "pending_review_task_titles": [str(task.get("title", "")) for task in pending_review_tasks],
        "pending_redemption_ids": [int(item["id"]) for item in pending_redemptions],
        "pending_redemption_labels": [
            _pending_redemption_label(item, members_by_user)
            for item in pending_redemptions
        ],
    }

    for child in member_children_data.values():
        child.pop("available_task_objects", None)
        child.pop("overdue_task_objects", None)

    calendar_tasks = [_calendar_task_payload(task) for task in tasks]

    return {
        "family": {
            "id": family_id,
            "name": family_name,
        },
        "me": me,
        "members": members,
        "summary": summary,
        "children": member_children_data,
        "tasks": calendar_tasks,
        "raw": {
            "task_count": len(tasks),
            "reward_count": len(rewards),
            "redemption_count": len(redemptions),
            "special_task_template_count": len(templates),
            "points_balance_count": len(balances),
            "reminder_count": len(reminders),
        },
    }


def _build_child_stats(
    *,
    member: dict[str, Any],
    tasks: list[dict[str, Any]],
    balances_by_user: dict[int, int],
    redemptions: list[dict[str, Any]],
    available_special_tasks: list[dict[str, Any]],
    now: datetime,
    tomorrow_start: datetime,
) -> dict[str, Any]:
    user_id = int(member["user_id"])
    own_tasks = [task for task in tasks if int(task.get("assignee_id", -1)) == user_id]
    own_visible_tasks = [task for task in own_tasks if task.get("is_active", True) is not False or task.get("status") == TASK_STATUS_APPROVED]

    actionable_tasks = _newest_recurring_entries(
        [
            task
            for task in own_visible_tasks
            if task.get("status") in {TASK_STATUS_OPEN, TASK_STATUS_REJECTED}
            and not (
                task.get("recurrence_type") == "weekly"
                and task.get("due_at_ts") is not None
                and task["due_at_ts"] > now
            )
        ],
        strategy="earliest_due",
    )

    overdue_tasks = [task for task in actionable_tasks if task.get("due_at_ts") is not None and task["due_at_ts"] < now]
    week_tasks = [
        task
        for task in actionable_tasks
        if task.get("recurrence_type") == "weekly"
        and not (task.get("due_at_ts") is not None and task["due_at_ts"] < now)
    ]
    due_today_tasks = []
    available_tasks = []
    for task in actionable_tasks:
        if task.get("recurrence_type") == "weekly":
            continue
        if task.get("special_template_id"):
            due_today_tasks.append(task)
            available_tasks.append(task)
            continue
        due_at = task.get("due_at_ts")
        if due_at is None:
            available_tasks.append(task)
            continue
        if now <= due_at < tomorrow_start:
            due_today_tasks.append(task)
            available_tasks.append(task)
            continue
        if due_at >= tomorrow_start:
            continue
        if due_at < now:
            available_tasks.append(task)

    waiting_tasks = _newest_recurring_entries(
        [task for task in own_visible_tasks if task.get("status") in {TASK_STATUS_SUBMITTED, TASK_STATUS_MISSED_SUBMITTED}]
    )
    completed_tasks = [
        task
        for task in own_visible_tasks
        if task.get("status") == TASK_STATUS_APPROVED and task.get("recurrence_type") == "none"
    ]
    pending_reward_requests = [
        entry
        for entry in redemptions
        if entry.get("status") == "pending" and int(entry.get("requested_by_id", -1)) == user_id
    ]

    return {
        "user_id": user_id,
        "display_name": str(member.get("display_name", user_id)),
        "role": member.get("role"),
        "is_active": bool(member.get("is_active", True)),
        "points_balance": balances_by_user.get(user_id, 0),
        "tasks_total": len(own_visible_tasks),
        "open_tasks": sum(1 for task in own_visible_tasks if task.get("status") == TASK_STATUS_OPEN),
        "rejected_tasks": sum(1 for task in own_visible_tasks if task.get("status") == TASK_STATUS_REJECTED),
        "due_today_tasks": len(due_today_tasks),
        "overdue_tasks": len(overdue_tasks),
        "available_tasks": len(available_tasks),
        "weekly_tasks": len(week_tasks),
        "submitted_tasks": sum(1 for task in own_visible_tasks if task.get("status") == TASK_STATUS_SUBMITTED),
        "missed_submissions": sum(1 for task in own_visible_tasks if task.get("status") == TASK_STATUS_MISSED_SUBMITTED),
        "pending_reviews": len(waiting_tasks),
        "approved_tasks": sum(1 for task in own_visible_tasks if task.get("status") == TASK_STATUS_APPROVED),
        "completed_tasks": len(completed_tasks),
        "pending_reward_requests": len(pending_reward_requests),
        "available_special_tasks": len(available_special_tasks),
        "available_task_ids": [int(task["id"]) for task in available_tasks],
        "available_task_titles": [str(task.get("title", "")) for task in available_tasks],
        "overdue_task_ids": [int(task["id"]) for task in overdue_tasks],
        "overdue_task_titles": [str(task.get("title", "")) for task in overdue_tasks],
        "pending_review_task_ids": [int(task["id"]) for task in waiting_tasks],
        "pending_review_task_titles": [str(task.get("title", "")) for task in waiting_tasks],
        "available_special_task_template_ids": [int(task["id"]) for task in available_special_tasks],
        "available_special_task_titles": [str(task.get("title", "")) for task in available_special_tasks],
        "available_task_objects": available_tasks,
        "overdue_task_objects": overdue_tasks,
    }


def _build_special_task_availability(
    templates: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
    child_user_ids: Any,
    now: datetime,
) -> dict[int, list[dict[str, Any]]]:
    result: dict[int, list[dict[str, Any]]] = defaultdict(list)
    task_index: dict[tuple[int, int], int] = defaultdict(int)
    for task in tasks:
        template_id = task.get("special_template_id")
        assignee_id = task.get("assignee_id")
        if not template_id or assignee_id is None:
            continue
        interval_type = next(
            (
                template.get("interval_type")
                for template in templates
                if int(template.get("id", -1)) == int(template_id)
            ),
            None,
        )
        if interval_type is None:
            continue
        start = _special_interval_start(str(interval_type), now)
        created_at = task.get("created_at_ts") or _parse_backend_datetime(task.get("created_at"))
        if created_at is not None and created_at >= start:
            task_index[(int(template_id), int(assignee_id))] += 1

    for raw_template in templates:
        if not raw_template.get("is_active", True):
            continue
        available_now, _ = _special_task_available_now(raw_template, now)
        if not available_now:
            continue
        max_claims = int(raw_template.get("max_claims_per_interval", 1))
        template_id = int(raw_template["id"])
        for user_id in child_user_ids:
            used = task_index.get((template_id, int(user_id)), 0)
            remaining = max(max_claims - used, 0)
            if remaining <= 0:
                continue
            result[int(user_id)].append(
                {
                    "id": template_id,
                    "title": raw_template.get("title", ""),
                    "interval_type": raw_template.get("interval_type"),
                    "remaining_count": remaining,
                    "used_count": used,
                }
            )
    return result


def _special_interval_start(interval_type: str, now: datetime) -> datetime:
    if interval_type == "daily":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if interval_type == "monthly":
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monday = now - timedelta(days=now.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


def _special_task_available_now(template: dict[str, Any], now: datetime) -> tuple[bool, str | None]:
    interval_type = template.get("interval_type")
    if interval_type != "daily":
        return True, None

    weekdays = sorted(set(int(value) for value in template.get("active_weekdays", []) if isinstance(value, int)))
    if weekdays and now.weekday() not in weekdays:
        return False, "weekday_mismatch"

    due_time = template.get("due_time_hhmm")
    if not due_time:
        return False, "missing_due_time"
    try:
        hour_raw, minute_raw = str(due_time).split(":", 1)
        deadline = now.replace(hour=int(hour_raw), minute=int(minute_raw), second=0, microsecond=0)
    except (TypeError, ValueError):
        return False, "invalid_due_time"

    if now > deadline:
        return False, "expired"
    return True, None


def _pending_redemption_label(entry: dict[str, Any], members_by_user: dict[int, dict[str, Any]]) -> str:
    requester = members_by_user.get(int(entry.get("requested_by_id", -1)))
    requester_name = requester.get("display_name") if requester else f"User {entry.get('requested_by_id')}"
    return f"{requester_name} (#{entry.get('reward_id')})"


def _calendar_task_payload(task: dict[str, Any]) -> dict[str, Any]:
    assignee_id = task.get("assignee_id")
    return {
        "id": int(task["id"]),
        "title": str(task.get("title", "")),
        "description": str(task.get("description") or ""),
        "assignee_id": int(assignee_id) if assignee_id is not None else None,
        "due_at": task.get("due_at_ts"),
        "status": str(task.get("status") or ""),
        "is_active": task.get("is_active", True) is not False,
    }


def _parse_backend_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = dt_util.parse_datetime(value)
    if parsed is None:
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
    return parsed.astimezone(dt_util.DEFAULT_TIME_ZONE)


def _recurring_task_key(task: dict[str, Any]) -> tuple[Any, ...] | None:
    if task.get("recurrence_type") == "none":
        return None
    return (
        int(task.get("assignee_id", -1)),
        str(task.get("title", "")),
        str(task.get("description") or ""),
        str(task.get("recurrence_type") or ""),
        int(task.get("special_template_id") or 0),
    )


def _task_activity_date(task: dict[str, Any]) -> datetime | None:
    return task.get("updated_at_ts") or task.get("created_at_ts") or task.get("due_at_ts")


def _due_sort_value(task: dict[str, Any]) -> float:
    due = task.get("due_at_ts")
    if due is None:
        return float("inf")
    return due.timestamp()


def _newest_recurring_entries(tasks: list[dict[str, Any]], strategy: str = "latest_activity") -> list[dict[str, Any]]:
    fixed: list[dict[str, Any]] = []
    latest_by_key: dict[tuple[Any, ...], dict[str, Any]] = {}
    for task in tasks:
        key = _recurring_task_key(task)
        if key is None:
            fixed.append(task)
            continue
        existing = latest_by_key.get(key)
        current_time = (_task_activity_date(task) or datetime(1970, 1, 1, tzinfo=dt_util.DEFAULT_TIME_ZONE)).timestamp()
        existing_time = (
            (_task_activity_date(existing) or datetime(1970, 1, 1, tzinfo=dt_util.DEFAULT_TIME_ZONE)).timestamp()
            if existing is not None
            else -1
        )
        if existing is None:
            latest_by_key[key] = task
            continue
        if strategy == "earliest_due":
            current_due = _due_sort_value(task)
            existing_due = _due_sort_value(existing)
            if current_due < existing_due or (current_due == existing_due and current_time >= existing_time):
                latest_by_key[key] = task
            continue
        if current_time >= existing_time:
            latest_by_key[key] = task
    return [*fixed, *latest_by_key.values()]
