from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN, TASK_STATUS_MISSED_SUBMITTED, TASK_STATUS_OPEN, TASK_STATUS_REJECTED, TASK_STATUS_SUBMITTED
from .coordinator import (
    HomeQuestsDataUpdateCoordinator,
    HomeQuestsRuntimeData,
    family_device_info,
    member_device_info,
)

CALENDAR_ACTIVE_STATUSES = {
    TASK_STATUS_OPEN,
    TASK_STATUS_REJECTED,
    TASK_STATUS_SUBMITTED,
    TASK_STATUS_MISSED_SUBMITTED,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime: HomeQuestsRuntimeData = hass.data[DOMAIN][entry.entry_id]
    coordinator = runtime.coordinator
    async_add_entities(_build_entities(coordinator, coordinator.data))

    known_user_ids = set(coordinator.data.get("children", {}).keys())

    @callback
    def _handle_update() -> None:
        new_user_ids = set(coordinator.data.get("children", {}).keys()) - known_user_ids
        if not new_user_ids:
            return
        known_user_ids.update(new_user_ids)
        async_add_entities([HomeQuestsChildCalendarEntity(coordinator, user_id) for user_id in sorted(new_user_ids)])

    entry.async_on_unload(coordinator.async_add_listener(_handle_update))


def _build_entities(
    coordinator: HomeQuestsDataUpdateCoordinator,
    data: dict[str, Any],
) -> list[CalendarEntity]:
    entities: list[CalendarEntity] = [HomeQuestsFamilyCalendarEntity(coordinator)]
    for user_id in sorted(data.get("children", {})):
        entities.append(HomeQuestsChildCalendarEntity(coordinator, user_id))
    return entities


def _task_to_calendar_event(task: dict[str, Any]) -> CalendarEvent | None:
    due_at = task.get("due_at")
    if due_at is None:
        return None
    return CalendarEvent(
        summary=task.get("title") or f"Aufgabe #{task.get('id')}",
        description=task.get("description") or "",
        start=due_at,
        end=due_at + timedelta(minutes=1),
    )


class HomeQuestsBaseCalendarEntity(CoordinatorEntity[HomeQuestsDataUpdateCoordinator], CalendarEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:calendar-check-outline"

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    def _iter_relevant_tasks(self) -> list[dict[str, Any]]:
        tasks = self.coordinator.data.get("tasks", [])
        return [
            task
            for task in tasks
            if task.get("is_active", True)
            and task.get("status") in CALENDAR_ACTIVE_STATUSES
            and task.get("due_at") is not None
        ]

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date,
        end_date,
    ) -> list[CalendarEvent]:
        events: list[CalendarEvent] = []
        for task in self._iter_relevant_tasks():
            due_at = task["due_at"]
            if start_date <= due_at <= end_date:
                calendar_event = _task_to_calendar_event(task)
                if calendar_event is not None:
                    events.append(calendar_event)
        events.sort(key=lambda event: event.start)
        return events


class HomeQuestsFamilyCalendarEntity(HomeQuestsBaseCalendarEntity):
    def __init__(self, coordinator: HomeQuestsDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"homequests_family_{coordinator.family_id}_calendar"
        self._attr_name = "Aufgaben-Kalender"

    @property
    def device_info(self) -> dict[str, Any]:
        return family_device_info(self.coordinator.family_id, self.coordinator.family_name)

    @property
    def event(self) -> CalendarEvent | None:
        now = dt_util.now()
        upcoming = [task for task in self._iter_relevant_tasks() if task["due_at"] >= now]
        upcoming.sort(key=lambda task: task["due_at"])
        if not upcoming:
            return None
        return _task_to_calendar_event(upcoming[0])


class HomeQuestsChildCalendarEntity(HomeQuestsBaseCalendarEntity):
    def __init__(self, coordinator: HomeQuestsDataUpdateCoordinator, user_id: int) -> None:
        super().__init__(coordinator)
        self._user_id = user_id
        self._attr_unique_id = f"homequests_family_{coordinator.family_id}_child_{user_id}_calendar"
        self._attr_name = "Aufgaben-Kalender"

    @property
    def _child(self) -> dict[str, Any]:
        return self.coordinator.data["children"][self._user_id]

    @property
    def available(self) -> bool:
        return super().available and self._user_id in self.coordinator.data.get("children", {})

    @property
    def device_info(self) -> dict[str, Any]:
        child = self._child
        return member_device_info(
            self.coordinator.family_id,
            self.coordinator.family_name,
            self._user_id,
            child["display_name"],
        )

    def _iter_relevant_tasks(self) -> list[dict[str, Any]]:
        return [task for task in super()._iter_relevant_tasks() if task.get("assignee_id") == self._user_id]

    @property
    def event(self) -> CalendarEvent | None:
        now = dt_util.now()
        upcoming = [task for task in self._iter_relevant_tasks() if task["due_at"] >= now]
        upcoming.sort(key=lambda task: task["due_at"])
        if not upcoming:
            return None
        return _task_to_calendar_event(upcoming[0])
