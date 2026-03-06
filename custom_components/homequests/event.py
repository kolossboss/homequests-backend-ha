from __future__ import annotations

from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_FAMILY_ID,
    ATTR_MEMBER_USER_ID,
    ATTR_TYPE,
    CONF_ENTRY_ID,
    DOMAIN,
    EVENT_HOMEQUESTS,
    HOMEQUESTS_EVENT_TYPES,
)
from .coordinator import (
    HomeQuestsDataUpdateCoordinator,
    HomeQuestsRuntimeData,
    family_device_info,
    member_device_info,
)


def _as_int(value: Any, default: int = -1) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


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
        async_add_entities([HomeQuestsChildEventEntity(coordinator, user_id) for user_id in sorted(new_user_ids)])

    entry.async_on_unload(coordinator.async_add_listener(_handle_update))


def _build_entities(
    coordinator: HomeQuestsDataUpdateCoordinator,
    data: dict[str, Any],
) -> list[EventEntity]:
    entities: list[EventEntity] = [HomeQuestsFamilyEventEntity(coordinator)]
    for user_id in sorted(data.get("children", {})):
        entities.append(HomeQuestsChildEventEntity(coordinator, user_id))
    return entities


class HomeQuestsBaseEventEntity(CoordinatorEntity[HomeQuestsDataUpdateCoordinator], EventEntity):
    _attr_has_entity_name = True
    _attr_event_types = list(HOMEQUESTS_EVENT_TYPES)
    _attr_icon = "mdi:flash"

    @callback
    def _async_matches_payload(self, payload: dict[str, Any]) -> bool:
        raise NotImplementedError

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.hass.bus.async_listen(EVENT_HOMEQUESTS, self._async_handle_homequests_event))

    @callback
    def _async_handle_homequests_event(self, event: Event) -> None:
        payload = event.data
        if payload.get(CONF_ENTRY_ID) != self.coordinator.entry.entry_id:
            return
        if not self._async_matches_payload(payload):
            return

        event_type = payload.get(ATTR_TYPE)
        if event_type not in HOMEQUESTS_EVENT_TYPES:
            return

        event_attributes = {key: value for key, value in payload.items() if key != ATTR_TYPE}
        self._trigger_event(event_type, event_attributes)
        self.async_write_ha_state()


class HomeQuestsFamilyEventEntity(HomeQuestsBaseEventEntity):
    def __init__(self, coordinator: HomeQuestsDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"homequests_family_{coordinator.family_id}_events"
        self._attr_name = "Ereignisse"

    @property
    def device_info(self) -> dict[str, Any]:
        return family_device_info(self.coordinator.family_id, self.coordinator.family_name)

    @callback
    def _async_matches_payload(self, payload: dict[str, Any]) -> bool:
        return _as_int(payload.get(ATTR_FAMILY_ID, -1)) == self.coordinator.family_id


class HomeQuestsChildEventEntity(HomeQuestsBaseEventEntity):
    def __init__(self, coordinator: HomeQuestsDataUpdateCoordinator, user_id: int) -> None:
        super().__init__(coordinator)
        self._user_id = user_id
        self._attr_unique_id = f"homequests_family_{coordinator.family_id}_child_{user_id}_events"
        self._attr_name = "Ereignisse"

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

    @callback
    def _async_matches_payload(self, payload: dict[str, Any]) -> bool:
        return _as_int(payload.get(ATTR_FAMILY_ID, -1)) == self.coordinator.family_id and _as_int(
            payload.get(ATTR_MEMBER_USER_ID, -1)
        ) == self._user_id
