from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import HomeQuestsAuthError, HomeQuestsClient, HomeQuestsConnectionError, HomeQuestsNoFamilyError
from .const import CONF_BASE_URL, CONF_FAMILY_ID, CONF_FAMILY_NAME, CONF_USER_ID, CONF_USER_NAME, DOMAIN


class HomeQuestsConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    _reauth_entry: ConfigEntry | None = None
    _reconfigure_entry: ConfigEntry | None = None

    async def async_step_user(self, user_input: Mapping[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await self._async_validate_input(user_input)
            except HomeQuestsAuthError:
                errors["base"] = "invalid_auth"
            except HomeQuestsConnectionError:
                errors["base"] = "cannot_connect"
            except HomeQuestsNoFamilyError:
                errors["base"] = "no_family"
            except Exception:
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info["unique_id"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=info["title"],
                    data=info["data"],
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self._build_schema(user_input),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        entry_id = self.context.get("entry_id")
        if entry_id is None:
            return self.async_abort(reason="unknown")

        self._reauth_entry = self.hass.config_entries.async_get_entry(entry_id)
        if self._reauth_entry is None:
            return self.async_abort(reason="unknown")
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: Mapping[str, Any] | None = None) -> FlowResult:
        if self._reauth_entry is None:
            return self.async_abort(reason="unknown")

        errors: dict[str, str] = {}
        defaults = {
            CONF_BASE_URL: self._reauth_entry.data[CONF_BASE_URL],
            CONF_USERNAME: self._reauth_entry.data[CONF_USERNAME],
            CONF_PASSWORD: self._reauth_entry.data[CONF_PASSWORD],
        }
        if user_input is not None:
            merged = {**defaults, **user_input}
            try:
                info = await self._async_validate_input(merged)
            except HomeQuestsAuthError:
                errors["base"] = "invalid_auth"
            except HomeQuestsConnectionError:
                errors["base"] = "cannot_connect"
            except HomeQuestsNoFamilyError:
                errors["base"] = "no_family"
            except Exception:
                errors["base"] = "unknown"
            else:
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry,
                    data=info["data"],
                    title=info["title"],
                    unique_id=info["unique_id"],
                )
                await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME, default=defaults[CONF_USERNAME]): str,
                    vol.Required(CONF_PASSWORD, default=defaults[CONF_PASSWORD]): str,
                }
            ),
            errors=errors,
            description_placeholders={CONF_FAMILY_NAME: self._reauth_entry.data.get(CONF_FAMILY_NAME, "HomeQuests")},
        )

    async def async_step_reconfigure(self, user_input: Mapping[str, Any] | None = None) -> FlowResult:
        entry_id = self.context.get("entry_id")
        if entry_id is not None:
            self._reconfigure_entry = self.hass.config_entries.async_get_entry(entry_id)
        if self._reconfigure_entry is None:
            self._reconfigure_entry = self._get_reconfigure_entry()
        if self._reconfigure_entry is None:
            return self.async_abort(reason="unknown")

        errors: dict[str, str] = {}
        defaults = {
            CONF_BASE_URL: self._reconfigure_entry.data[CONF_BASE_URL],
            CONF_USERNAME: self._reconfigure_entry.data[CONF_USERNAME],
            CONF_PASSWORD: self._reconfigure_entry.data[CONF_PASSWORD],
        }
        if user_input is not None:
            try:
                info = await self._async_validate_input(user_input)
            except HomeQuestsAuthError:
                errors["base"] = "invalid_auth"
            except HomeQuestsConnectionError:
                errors["base"] = "cannot_connect"
            except HomeQuestsNoFamilyError:
                errors["base"] = "no_family"
            except Exception:
                errors["base"] = "unknown"
            else:
                self.hass.config_entries.async_update_entry(
                    self._reconfigure_entry,
                    data=info["data"],
                    title=info["title"],
                    unique_id=info["unique_id"],
                )
                await self.hass.config_entries.async_reload(self._reconfigure_entry.entry_id)
                return self.async_abort(reason="reconfigure_successful")

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self._build_schema(defaults),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry):
        return None

    def _build_schema(self, defaults: Mapping[str, Any] | None = None) -> vol.Schema:
        defaults = defaults or {}
        return vol.Schema(
            {
                vol.Required(CONF_BASE_URL, default=defaults.get(CONF_BASE_URL, "http://homequests.local:8000")): str,
                vol.Required(CONF_USERNAME, default=defaults.get(CONF_USERNAME, "")): str,
                vol.Required(CONF_PASSWORD, default=defaults.get(CONF_PASSWORD, "")): str,
            }
        )

    async def _async_validate_input(self, user_input: Mapping[str, Any]) -> dict[str, Any]:
        base_url = normalize_base_url(str(user_input[CONF_BASE_URL]))
        username = str(user_input[CONF_USERNAME]).strip()
        password = str(user_input[CONF_PASSWORD])

        session = async_get_clientsession(self.hass)
        client = HomeQuestsClient(session, base_url, username, password)
        context = await client.async_get_setup_context()
        family = context["family"]
        me = context["me"]
        family_id = int(family["id"])
        family_name = str(family.get("name", f"Familie {family_id}"))
        unique_id = build_unique_id(base_url, family_id)

        return {
            "title": f"HomeQuests ({family_name})",
            "unique_id": unique_id,
            "data": {
                CONF_BASE_URL: base_url,
                CONF_USERNAME: username,
                CONF_PASSWORD: password,
                CONF_FAMILY_ID: family_id,
                CONF_FAMILY_NAME: family_name,
                CONF_USER_ID: int(me["id"]),
                CONF_USER_NAME: str(me.get("display_name", username)),
            },
        }

    def _get_reconfigure_entry(self) -> ConfigEntry | None:
        if self.context.get("entry_id"):
            return None
        entries = self._async_current_entries()
        if len(entries) == 1:
            return entries[0]
        return None

def normalize_base_url(value: str) -> str:
    raw = value.strip().rstrip("/")
    parsed = urlparse(raw)
    if not parsed.scheme:
        raw = f"http://{raw}"
        parsed = urlparse(raw)
    if not parsed.netloc:
        raise HomeQuestsConnectionError("Invalid backend URL")
    return raw.rstrip("/")


def build_unique_id(base_url: str, family_id: int) -> str:
    parsed = urlparse(base_url)
    netloc = (parsed.netloc or parsed.path).lower()
    path = parsed.path.rstrip("/").lower()
    return f"{netloc}{path}::family::{family_id}"
