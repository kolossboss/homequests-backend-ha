from __future__ import annotations

from collections.abc import Callable
import logging
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .api import HomeQuestsApiError, HomeQuestsAuthError, HomeQuestsClient, HomeQuestsConnectionError
from .const import (
    CONF_BASE_URL,
    CONF_ENTRY_ID,
    CONF_FAMILY_ID,
    CONF_PASSWORD,
    CONF_USERNAME,
    DOMAIN,
    PLATFORMS,
    SERVICE_ADJUST_POINTS,
    SERVICE_REFRESH,
    SERVICE_REPORT_TASK_MISSED,
    SERVICE_REVIEW_MISSED_TASK,
    SERVICE_REVIEW_REDEMPTION,
    SERVICE_REVIEW_TASK,
    SERVICE_SUBMIT_TASK,
)
from .coordinator import HomeQuestsDataUpdateCoordinator, HomeQuestsRuntimeData

_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
DATA_FRONTEND_REGISTERED = f"{DOMAIN}_frontend_registered"
FRONTEND_STATIC_URL_PATH = "/homequests_frontend"
FRONTEND_DIRECTORY_NAME = "frontend"

SERVICE_SCHEMAS = {
    SERVICE_REFRESH: vol.Schema({vol.Optional(CONF_ENTRY_ID): cv.string}),
    SERVICE_REVIEW_TASK: vol.Schema(
        {
            vol.Optional(CONF_ENTRY_ID): cv.string,
            vol.Required("task_id"): vol.Coerce(int),
            vol.Required("decision"): vol.In(["approved", "rejected"]),
            vol.Optional("comment"): vol.Any(None, cv.string),
        }
    ),
    SERVICE_REVIEW_MISSED_TASK: vol.Schema(
        {
            vol.Optional(CONF_ENTRY_ID): cv.string,
            vol.Required("task_id"): vol.Coerce(int),
            vol.Required("action"): vol.In(["delete", "penalty"]),
            vol.Optional("comment"): vol.Any(None, cv.string),
        }
    ),
    SERVICE_REVIEW_REDEMPTION: vol.Schema(
        {
            vol.Optional(CONF_ENTRY_ID): cv.string,
            vol.Required("redemption_id"): vol.Coerce(int),
            vol.Required("decision"): vol.In(["approved", "rejected"]),
            vol.Optional("comment"): vol.Any(None, cv.string),
        }
    ),
    SERVICE_ADJUST_POINTS: vol.Schema(
        {
            vol.Optional(CONF_ENTRY_ID): cv.string,
            vol.Required("user_id"): vol.Coerce(int),
            vol.Required("points_delta"): vol.Coerce(int),
            vol.Required("description"): cv.string,
        }
    ),
    SERVICE_SUBMIT_TASK: vol.Schema(
        {
            vol.Optional(CONF_ENTRY_ID): cv.string,
            vol.Required("task_id"): vol.Coerce(int),
            vol.Optional("note"): vol.Any(None, cv.string),
        }
    ),
    SERVICE_REPORT_TASK_MISSED: vol.Schema(
        {
            vol.Optional(CONF_ENTRY_ID): cv.string,
            vol.Required("task_id"): vol.Coerce(int),
        }
    ),
}


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    hass.data.setdefault(DOMAIN, {})
    await _async_register_frontend_assets(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = aiohttp_client.async_get_clientsession(hass)
    api = HomeQuestsClient(
        session=session,
        base_url=entry.data[CONF_BASE_URL],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
    )
    coordinator = HomeQuestsDataUpdateCoordinator(hass, entry, api)
    runtime_data = HomeQuestsRuntimeData(api=api, coordinator=coordinator)

    hass.data[DOMAIN][entry.entry_id] = runtime_data
    # runtime_data is not available on very old HA core versions.
    try:
        entry.runtime_data = runtime_data
    except AttributeError:
        pass
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryAuthFailed:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        raise

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await coordinator.async_start_live_listener()
    await _async_register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    runtime: HomeQuestsRuntimeData | None = hass.data[DOMAIN].get(entry.entry_id)
    if runtime is not None:
        await runtime.coordinator.async_stop_live_listener()
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    if not hass.data[DOMAIN]:
        for service_name in SERVICE_SCHEMAS:
            if hass.services.has_service(DOMAIN, service_name):
                hass.services.async_remove(DOMAIN, service_name)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_REFRESH):
        return

    async def refresh_service(call: ServiceCall) -> None:
        runtime = _resolve_runtime_data(hass, call)
        await runtime.coordinator.async_manual_refresh()

    async def review_task_service(call: ServiceCall) -> None:
        runtime = _resolve_runtime_data(hass, call)
        await _async_api_call(
            runtime,
            lambda: runtime.api.async_review_task(
                task_id=call.data["task_id"],
                decision=call.data["decision"],
                comment=call.data.get("comment"),
            ),
        )

    async def review_missed_task_service(call: ServiceCall) -> None:
        runtime = _resolve_runtime_data(hass, call)
        await _async_api_call(
            runtime,
            lambda: runtime.api.async_review_missed_task(
                task_id=call.data["task_id"],
                action=call.data["action"],
                comment=call.data.get("comment"),
            ),
        )

    async def review_redemption_service(call: ServiceCall) -> None:
        runtime = _resolve_runtime_data(hass, call)
        await _async_api_call(
            runtime,
            lambda: runtime.api.async_review_redemption(
                redemption_id=call.data["redemption_id"],
                decision=call.data["decision"],
                comment=call.data.get("comment"),
            ),
        )

    async def adjust_points_service(call: ServiceCall) -> None:
        runtime = _resolve_runtime_data(hass, call)
        await _async_api_call(
            runtime,
            lambda: runtime.api.async_adjust_points(
                family_id=int(runtime.coordinator.family_id),
                user_id=call.data["user_id"],
                points_delta=call.data["points_delta"],
                description=call.data["description"],
            ),
        )

    async def submit_task_service(call: ServiceCall) -> None:
        runtime = _resolve_runtime_data(hass, call)
        await _async_api_call(
            runtime,
            lambda: runtime.api.async_submit_task(
                task_id=call.data["task_id"],
                note=call.data.get("note"),
            ),
        )

    async def report_task_missed_service(call: ServiceCall) -> None:
        runtime = _resolve_runtime_data(hass, call)
        await _async_api_call(
            runtime,
            lambda: runtime.api.async_report_task_missed(task_id=call.data["task_id"]),
        )

    service_handlers: dict[str, Callable[[ServiceCall], Any]] = {
        SERVICE_REFRESH: refresh_service,
        SERVICE_REVIEW_TASK: review_task_service,
        SERVICE_REVIEW_MISSED_TASK: review_missed_task_service,
        SERVICE_REVIEW_REDEMPTION: review_redemption_service,
        SERVICE_ADJUST_POINTS: adjust_points_service,
        SERVICE_SUBMIT_TASK: submit_task_service,
        SERVICE_REPORT_TASK_MISSED: report_task_missed_service,
    }

    for service_name, handler in service_handlers.items():
        hass.services.async_register(
            DOMAIN,
            service_name,
            handler,
            schema=SERVICE_SCHEMAS[service_name],
        )


async def _async_api_call(runtime: HomeQuestsRuntimeData, action: Callable[[], Any]) -> None:
    try:
        await action()
    except HomeQuestsAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except (HomeQuestsApiError, HomeQuestsConnectionError) as err:
        raise HomeAssistantError(str(err)) from err
    await runtime.coordinator.async_manual_refresh()


def _resolve_runtime_data(hass: HomeAssistant, call: ServiceCall) -> HomeQuestsRuntimeData:
    configured = hass.data.get(DOMAIN, {})
    if not configured:
        raise HomeAssistantError("Keine HomeQuests-Integration geladen")

    entry_id = call.data.get(CONF_ENTRY_ID)
    if entry_id is not None:
        runtime = configured.get(entry_id)
        if runtime is None:
            raise HomeAssistantError(f"Config Entry {entry_id} wurde nicht gefunden")
        return runtime

    if len(configured) == 1:
        return next(iter(configured.values()))

    raise HomeAssistantError("Bitte 'entry_id' angeben, weil mehrere HomeQuests-Einträge geladen sind")


async def _async_register_frontend_assets(hass: HomeAssistant) -> None:
    if hass.data.get(DATA_FRONTEND_REGISTERED):
        return

    frontend_path = Path(__file__).parent / FRONTEND_DIRECTORY_NAME
    if not frontend_path.exists():
        return

    try:
        if hasattr(hass.http, "async_register_static_paths"):
            await hass.http.async_register_static_paths(
                [StaticPathConfig(FRONTEND_STATIC_URL_PATH, str(frontend_path), cache_headers=False)]
            )
        else:
            hass.http.register_static_path(FRONTEND_STATIC_URL_PATH, str(frontend_path), cache_headers=False)
    except Exception as err:  # pragma: no cover - defensive
        _LOGGER.warning("HomeQuests frontend assets konnten nicht registriert werden: %s", err)
        return

    hass.data[DATA_FRONTEND_REGISTERED] = True
