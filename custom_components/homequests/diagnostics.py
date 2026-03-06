from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, REDACT_KEYS
from .coordinator import HomeQuestsRuntimeData


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    runtime: HomeQuestsRuntimeData = hass.data[DOMAIN][entry.entry_id]
    payload = {
        "entry": dict(entry.data),
        "coordinator": runtime.coordinator.data,
        "api": {
            "base_url": runtime.api.base_url,
            "username": runtime.api.username,
        },
    }
    return async_redact_data(payload, REDACT_KEYS)
