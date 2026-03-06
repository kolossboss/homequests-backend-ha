from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription, SensorStateClass
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

COUNT_STATE_CLASS = SensorStateClass.MEASUREMENT


@dataclass(frozen=True, kw_only=True)
class HomeQuestsSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], Any]
    attributes_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None
    unit: str | None = None


GLOBAL_SENSORS: tuple[HomeQuestsSensorDescription, ...] = (
    HomeQuestsSensorDescription(key="tasks_total", name="Aufgaben gesamt", icon="mdi:clipboard-text-outline", value_fn=lambda data: data["summary"]["tasks_total"]),
    HomeQuestsSensorDescription(key="special_task_templates_total", name="Sonderaufgaben gesamt", icon="mdi:star-box-outline", value_fn=lambda data: data["summary"]["special_task_templates_total"]),
    HomeQuestsSensorDescription(key="special_task_templates_active", name="Sonderaufgaben aktiv", icon="mdi:star-check-outline", value_fn=lambda data: data["summary"]["special_task_templates_active"]),
    HomeQuestsSensorDescription(key="tasks_open_total", name="Offene Aufgaben", icon="mdi:clipboard-alert-outline", value_fn=lambda data: data["summary"]["tasks_open_total"]),
    HomeQuestsSensorDescription(key="tasks_rejected_total", name="Abgelehnte Aufgaben", icon="mdi:clipboard-remove-outline", value_fn=lambda data: data["summary"]["tasks_rejected_total"]),
    HomeQuestsSensorDescription(key="tasks_completed_total", name="Abgeschlossene Aufgaben", icon="mdi:clipboard-check-outline", value_fn=lambda data: data["summary"]["tasks_completed_total"]),
    HomeQuestsSensorDescription(key="tasks_overdue_total", name="Überfällige Aufgaben", icon="mdi:calendar-alert-outline", value_fn=lambda data: data["summary"]["tasks_overdue_total"]),
    HomeQuestsSensorDescription(key="tasks_submitted_total", name="Eingereichte Aufgaben", icon="mdi:clipboard-clock-outline", value_fn=lambda data: data["summary"]["tasks_submitted_total"]),
    HomeQuestsSensorDescription(key="tasks_missed_submitted_total", name="Als nicht erledigt gemeldet", icon="mdi:clipboard-off-outline", value_fn=lambda data: data["summary"]["tasks_missed_submitted_total"]),
    HomeQuestsSensorDescription(
        key="tasks_pending_review_total",
        name="Aufgaben in Prüfung",
        icon="mdi:account-eye-outline",
        value_fn=lambda data: data["summary"]["tasks_pending_review_total"],
        attributes_fn=lambda data: {
            "task_ids": data["summary"]["pending_review_task_ids"],
            "task_titles": data["summary"]["pending_review_task_titles"],
        },
    ),
    HomeQuestsSensorDescription(key="tasks_actionable_total", name="Verfügbare Aufgaben", icon="mdi:playlist-check", value_fn=lambda data: data["summary"]["tasks_actionable_total"]),
    HomeQuestsSensorDescription(key="rewards_active_total", name="Aktive Belohnungen", icon="mdi:gift-outline", value_fn=lambda data: data["summary"]["rewards_active_total"]),
    HomeQuestsSensorDescription(
        key="pending_reward_redemptions_total",
        name="Offene Belohnungsanfragen",
        icon="mdi:cash-clock",
        value_fn=lambda data: data["summary"]["pending_reward_redemptions_total"],
        attributes_fn=lambda data: {
            "redemption_ids": data["summary"]["pending_redemption_ids"],
            "requests": data["summary"]["pending_redemption_labels"],
        },
    ),
    HomeQuestsSensorDescription(key="upcoming_task_reminders_total", name="Anstehende Erinnerungen (24h)", icon="mdi:bell-outline", value_fn=lambda data: data["summary"]["upcoming_task_reminders_total"]),
)


CHILD_SENSORS: tuple[HomeQuestsSensorDescription, ...] = (
    HomeQuestsSensorDescription(key="open_tasks", name="Offene Aufgaben", icon="mdi:clipboard-alert-outline", value_fn=lambda child: child["open_tasks"]),
    HomeQuestsSensorDescription(key="rejected_tasks", name="Abgelehnte Aufgaben", icon="mdi:clipboard-remove-outline", value_fn=lambda child: child["rejected_tasks"]),
    HomeQuestsSensorDescription(key="due_today_tasks", name="Heute fällige Aufgaben", icon="mdi:calendar-today-outline", value_fn=lambda child: child["due_today_tasks"]),
    HomeQuestsSensorDescription(
        key="available_tasks",
        name="Verfügbare Aufgaben",
        icon="mdi:playlist-check",
        value_fn=lambda child: child["available_tasks"],
        attributes_fn=lambda child: {"task_ids": child["available_task_ids"], "task_titles": child["available_task_titles"]},
    ),
    HomeQuestsSensorDescription(
        key="overdue_tasks",
        name="Überfällige Aufgaben",
        icon="mdi:calendar-alert-outline",
        value_fn=lambda child: child["overdue_tasks"],
        attributes_fn=lambda child: {"task_ids": child["overdue_task_ids"], "task_titles": child["overdue_task_titles"]},
    ),
    HomeQuestsSensorDescription(key="submitted_tasks", name="Eingereichte Aufgaben", icon="mdi:clipboard-clock-outline", value_fn=lambda child: child["submitted_tasks"]),
    HomeQuestsSensorDescription(key="missed_submissions", name="Nicht erledigt gemeldet", icon="mdi:clipboard-off-outline", value_fn=lambda child: child["missed_submissions"]),
    HomeQuestsSensorDescription(
        key="pending_reviews",
        name="Aufgaben in Prüfung",
        icon="mdi:account-eye-outline",
        value_fn=lambda child: child["pending_reviews"],
        attributes_fn=lambda child: {"task_ids": child["pending_review_task_ids"], "task_titles": child["pending_review_task_titles"]},
    ),
    HomeQuestsSensorDescription(key="completed_tasks", name="Abgeschlossene Einzelaufgaben", icon="mdi:clipboard-check-outline", value_fn=lambda child: child["completed_tasks"]),
    HomeQuestsSensorDescription(key="points_balance", name="Punktestand", icon="mdi:star-circle-outline", value_fn=lambda child: child["points_balance"], unit="Punkte"),
    HomeQuestsSensorDescription(key="pending_reward_requests", name="Offene Belohnungsanfragen", icon="mdi:gift-open-outline", value_fn=lambda child: child["pending_reward_requests"]),
    HomeQuestsSensorDescription(
        key="available_special_tasks",
        name="Verfügbare Sonderaufgaben",
        icon="mdi:star-box-outline",
        value_fn=lambda child: child["available_special_tasks"],
        attributes_fn=lambda child: {
            "template_ids": child["available_special_task_template_ids"],
            "titles": child["available_special_task_titles"],
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime: HomeQuestsRuntimeData = hass.data[DOMAIN][entry.entry_id]
    coordinator = runtime.coordinator
    async_add_entities(_build_sensor_entities(coordinator, coordinator.data))

    known_user_ids = set(coordinator.data.get("children", {}).keys())

    @callback
    def _handle_update() -> None:
        new_user_ids = set(coordinator.data.get("children", {}).keys()) - known_user_ids
        if not new_user_ids:
            return
        known_user_ids.update(new_user_ids)
        new_entities: list[SensorEntity] = []
        for user_id in sorted(new_user_ids):
            child = coordinator.data["children"][user_id]
            new_entities.extend(_build_child_sensor_entities(coordinator, child))
        async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_handle_update))


def _build_sensor_entities(coordinator: HomeQuestsDataUpdateCoordinator, data: dict[str, Any]) -> list[SensorEntity]:
    entities: list[SensorEntity] = [HomeQuestsFamilySensor(coordinator, description) for description in GLOBAL_SENSORS]
    for child in data.get("children", {}).values():
        entities.extend(_build_child_sensor_entities(coordinator, child))
    return entities


def _build_child_sensor_entities(
    coordinator: HomeQuestsDataUpdateCoordinator,
    child: dict[str, Any],
) -> list[SensorEntity]:
    return [HomeQuestsChildSensor(coordinator, child["user_id"], description) for description in CHILD_SENSORS]


class HomeQuestsBaseEntity(CoordinatorEntity[HomeQuestsDataUpdateCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: HomeQuestsDataUpdateCoordinator) -> None:
        super().__init__(coordinator)

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success


class HomeQuestsFamilySensor(HomeQuestsBaseEntity, SensorEntity):
    entity_description: HomeQuestsSensorDescription

    def __init__(self, coordinator: HomeQuestsDataUpdateCoordinator, description: HomeQuestsSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"homequests_family_{coordinator.family_id}_{description.key}"
        self._attr_native_unit_of_measurement = description.unit
        self._attr_state_class = COUNT_STATE_CLASS

    @property
    def device_info(self) -> dict[str, Any]:
        return family_device_info(self.coordinator.family_id, self.coordinator.family_name)

    @property
    def name(self) -> str:
        return self.entity_description.name

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        base = {"family_id": self.coordinator.family_id, "family_name": self.coordinator.family_name}
        if self.entity_description.attributes_fn is not None:
            base.update(self.entity_description.attributes_fn(self.coordinator.data))
        return base


class HomeQuestsChildSensor(HomeQuestsBaseEntity, SensorEntity):
    entity_description: HomeQuestsSensorDescription

    def __init__(
        self,
        coordinator: HomeQuestsDataUpdateCoordinator,
        user_id: int,
        description: HomeQuestsSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._user_id = user_id
        self._attr_unique_id = f"homequests_family_{coordinator.family_id}_child_{user_id}_{description.key}"
        self._attr_native_unit_of_measurement = description.unit
        self._attr_state_class = COUNT_STATE_CLASS

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

    @property
    def name(self) -> str:
        return self.entity_description.name

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self._child)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        child = self._child
        base = {
            "family_id": self.coordinator.family_id,
            "family_name": self.coordinator.family_name,
            "user_id": self._user_id,
            "display_name": child["display_name"],
            "role": child["role"],
            "is_active": child["is_active"],
        }
        if self.entity_description.attributes_fn is not None:
            base.update(self.entity_description.attributes_fn(child))
        return base
