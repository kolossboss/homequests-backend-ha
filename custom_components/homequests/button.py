from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HomeQuestsDataUpdateCoordinator, HomeQuestsRuntimeData, family_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime: HomeQuestsRuntimeData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([HomeQuestsRefreshButton(runtime.coordinator)])


class HomeQuestsRefreshButton(CoordinatorEntity[HomeQuestsDataUpdateCoordinator], ButtonEntity):
    _attr_has_entity_name = True
    _attr_name = "Jetzt aktualisieren"
    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator: HomeQuestsDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"homequests_family_{coordinator.family_id}_refresh"

    @property
    def device_info(self) -> dict[str, object]:
        return family_device_info(self.coordinator.family_id, self.coordinator.family_name)

    async def async_press(self) -> None:
        await self.coordinator.async_manual_refresh()
