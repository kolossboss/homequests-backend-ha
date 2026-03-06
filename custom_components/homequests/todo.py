from __future__ import annotations

from typing import Any

from homeassistant.components.todo import TodoItem, TodoItemStatus, TodoListEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import (
    HomeQuestsDataUpdateCoordinator,
    HomeQuestsRuntimeData,
    family_device_info,
    member_device_info,
)


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
        async_add_entities([HomeQuestsChildTodoEntity(coordinator, user_id) for user_id in sorted(new_user_ids)])

    entry.async_on_unload(coordinator.async_add_listener(_handle_update))


def _build_entities(
    coordinator: HomeQuestsDataUpdateCoordinator,
    data: dict[str, Any],
) -> list[TodoListEntity]:
    entities: list[TodoListEntity] = [HomeQuestsFamilyTodoEntity(coordinator)]
    for user_id in sorted(data.get("children", {})):
        entities.append(HomeQuestsChildTodoEntity(coordinator, user_id))
    return entities


def _build_todo_items(task_ids: list[int], task_titles: list[str]) -> list[TodoItem]:
    items: list[TodoItem] = []
    for task_id, task_title in zip(task_ids, task_titles, strict=False):
        items.append(
            TodoItem(
                uid=str(task_id),
                summary=(task_title or f"Aufgabe #{task_id}"),
                status=TodoItemStatus.NEEDS_ACTION,
            )
        )
    return items


class HomeQuestsBaseTodoEntity(CoordinatorEntity[HomeQuestsDataUpdateCoordinator], TodoListEntity):
    _attr_has_entity_name = True
    _attr_supported_features = 0
    _attr_icon = "mdi:format-list-checks"

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success


class HomeQuestsFamilyTodoEntity(HomeQuestsBaseTodoEntity):
    def __init__(self, coordinator: HomeQuestsDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"homequests_family_{coordinator.family_id}_pending_reviews_todo"
        self._attr_name = "Aufgaben in Prüfung"

    @property
    def device_info(self) -> dict[str, Any]:
        return family_device_info(self.coordinator.family_id, self.coordinator.family_name)

    @property
    def todo_items(self) -> list[TodoItem]:
        summary = self.coordinator.data.get("summary", {})
        return _build_todo_items(
            list(summary.get("pending_review_task_ids", [])),
            list(summary.get("pending_review_task_titles", [])),
        )


class HomeQuestsChildTodoEntity(HomeQuestsBaseTodoEntity):
    def __init__(self, coordinator: HomeQuestsDataUpdateCoordinator, user_id: int) -> None:
        super().__init__(coordinator)
        self._user_id = user_id
        self._attr_unique_id = f"homequests_family_{coordinator.family_id}_child_{user_id}_available_todo"
        self._attr_name = "Verfügbare Aufgaben"

    @property
    def available(self) -> bool:
        return super().available and self._user_id in self.coordinator.data.get("children", {})

    @property
    def _child(self) -> dict[str, Any]:
        return self.coordinator.data["children"][self._user_id]

    @property
    def device_info(self) -> dict[str, Any]:
        child = self._child
        return member_device_info(
            self.coordinator.family_id,
            self.coordinator.family_name,
            self._user_id,
            child["display_name"],
        )

    @property
    def todo_items(self) -> list[TodoItem]:
        child = self._child
        return _build_todo_items(
            list(child.get("available_task_ids", [])),
            list(child.get("available_task_titles", [])),
        )
