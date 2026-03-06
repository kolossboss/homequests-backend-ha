from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorEntityDescription
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


@dataclass(frozen=True, kw_only=True)
class HomeQuestsBinarySensorDescription(BinarySensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], bool]


GLOBAL_BINARY_SENSORS: tuple[HomeQuestsBinarySensorDescription, ...] = (
    HomeQuestsBinarySensorDescription(key="has_overdue_tasks", name="Hat überfällige Aufgaben", icon="mdi:calendar-alert-outline", value_fn=lambda data: data["summary"]["tasks_overdue_total"] > 0),
    HomeQuestsBinarySensorDescription(key="has_pending_task_reviews", name="Hat offene Aufgaben-Freigaben", icon="mdi:account-eye-outline", value_fn=lambda data: data["summary"]["tasks_pending_review_total"] > 0),
    HomeQuestsBinarySensorDescription(key="has_pending_reward_requests", name="Hat offene Belohnungsanfragen", icon="mdi:gift-open-outline", value_fn=lambda data: data["summary"]["pending_reward_redemptions_total"] > 0),
)

CHILD_BINARY_SENSORS: tuple[HomeQuestsBinarySensorDescription, ...] = (
    HomeQuestsBinarySensorDescription(key="has_overdue_tasks", name="Hat überfällige Aufgaben", icon="mdi:calendar-alert-outline", value_fn=lambda child: child["overdue_tasks"] > 0),
    HomeQuestsBinarySensorDescription(key="has_pending_reviews", name="Hat Aufgaben in Prüfung", icon="mdi:account-eye-outline", value_fn=lambda child: child["pending_reviews"] > 0),
    HomeQuestsBinarySensorDescription(key="has_available_special_tasks", name="Hat verfügbare Sonderaufgaben", icon="mdi:star-box-outline", value_fn=lambda child: child["available_special_tasks"] > 0),
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
        entities: list[BinarySensorEntity] = []
        for user_id in sorted(new_user_ids):
            entities.extend(_build_child_entities(coordinator, user_id))
        async_add_entities(entities)

    entry.async_on_unload(coordinator.async_add_listener(_handle_update))


def _build_entities(coordinator: HomeQuestsDataUpdateCoordinator, data: dict[str, Any]) -> list[BinarySensorEntity]:
    entities: list[BinarySensorEntity] = [HomeQuestsFamilyBinarySensor(coordinator, description) for description in GLOBAL_BINARY_SENSORS]
    for user_id in data.get("children", {}):
        entities.extend(_build_child_entities(coordinator, user_id))
    return entities


def _build_child_entities(coordinator: HomeQuestsDataUpdateCoordinator, user_id: int) -> list[BinarySensorEntity]:
    return [HomeQuestsChildBinarySensor(coordinator, user_id, description) for description in CHILD_BINARY_SENSORS]


class HomeQuestsBaseBinarySensor(CoordinatorEntity[HomeQuestsDataUpdateCoordinator], BinarySensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: HomeQuestsDataUpdateCoordinator) -> None:
        super().__init__(coordinator)


class HomeQuestsFamilyBinarySensor(HomeQuestsBaseBinarySensor):
    entity_description: HomeQuestsBinarySensorDescription

    def __init__(self, coordinator: HomeQuestsDataUpdateCoordinator, description: HomeQuestsBinarySensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"homequests_family_{coordinator.family_id}_{description.key}"

    @property
    def device_info(self) -> dict[str, Any]:
        return family_device_info(self.coordinator.family_id, self.coordinator.family_name)

    @property
    def name(self) -> str:
        return self.entity_description.name

    @property
    def is_on(self) -> bool:
        return self.entity_description.value_fn(self.coordinator.data)


class HomeQuestsChildBinarySensor(HomeQuestsBaseBinarySensor):
    entity_description: HomeQuestsBinarySensorDescription

    def __init__(self, coordinator: HomeQuestsDataUpdateCoordinator, user_id: int, description: HomeQuestsBinarySensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._user_id = user_id
        self._attr_unique_id = f"homequests_family_{coordinator.family_id}_child_{user_id}_{description.key}"

    @property
    def _child(self) -> dict[str, Any]:
        return self.coordinator.data["children"][self._user_id]

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self._user_id in self.coordinator.data.get("children", {})

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
    def name(self) -> str:
        return self.entity_description.name

    @property
    def is_on(self) -> bool:
        return self.entity_description.value_fn(self._child)
