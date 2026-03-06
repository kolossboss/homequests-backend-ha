from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import HomeQuestsAuthError, HomeQuestsClient, HomeQuestsConnectionError, HomeQuestsNoFamilyError
from .const import CONF_BASE_URL, CONF_FAMILY_ID, CONF_FAMILY_NAME, CONF_USER_ID, CONF_USER_NAME, DOMAIN


class HomeQuestsConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    _reauth_entry: ConfigEntry | None = None
    _reconfigure_entry: ConfigEntry | None = None
    _pending_setup_context: dict[str, Any] | None = None

    async def async_step_user(self, user_input: Mapping[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                setup_context = await self._async_authenticate_input(user_input)
            except HomeQuestsAuthError:
                errors["base"] = "invalid_auth"
            except HomeQuestsConnectionError:
                errors["base"] = "cannot_connect"
            except HomeQuestsNoFamilyError:
                errors["base"] = "no_family"
            except Exception:
                errors["base"] = "unknown"
            else:
                families = setup_context["families"]
                if len(families) == 1:
                    info = self._build_entry_info(setup_context, int(families[0]["id"]))
                    await self.async_set_unique_id(info["unique_id"])
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=info["title"],
                        data=info["data"],
                    )
                self._pending_setup_context = setup_context
                return await self.async_step_family()

        return self.async_show_form(
            step_id="user",
            data_schema=self._build_schema(user_input),
            errors=errors,
        )

    async def async_step_family(self, user_input: Mapping[str, Any] | None = None):
        if self._pending_setup_context is None:
            return self.async_abort(reason="unknown")

        families = self._pending_setup_context["families"]
        family_options = {
            str(int(family["id"])): str(family.get("name", f"Familie {int(family['id'])}"))
            for family in families
        }
        if not family_options:
            self._pending_setup_context = None
            return self.async_abort(reason="unknown")

        errors: dict[str, str] = {}
        if user_input is not None:
            selected_family_id = str(user_input.get(CONF_FAMILY_ID, ""))
            if selected_family_id not in family_options:
                errors["base"] = "unknown_family"
            else:
                info = self._build_entry_info(self._pending_setup_context, int(selected_family_id))
                self._pending_setup_context = None
                await self.async_set_unique_id(info["unique_id"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=info["title"],
                    data=info["data"],
                )

        default_family_id = str(user_input.get(CONF_FAMILY_ID)) if user_input else next(iter(family_options))
        return self.async_show_form(
            step_id="family",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_FAMILY_ID, default=default_family_id): vol.In(family_options),
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]):
        entry_id = self.context.get("entry_id")
        if entry_id is None:
            return self.async_abort(reason="unknown")

        self._reauth_entry = self.hass.config_entries.async_get_entry(entry_id)
        if self._reauth_entry is None:
            return self.async_abort(reason="unknown")
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: Mapping[str, Any] | None = None):
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
                info = await self._async_validate_input(
                    merged,
                    expected_family_id=int(self._reauth_entry.data[CONF_FAMILY_ID]),
                )
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

    async def async_step_reconfigure(self, user_input: Mapping[str, Any] | None = None):
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
                info = await self._async_validate_input(
                    user_input,
                    expected_family_id=int(self._reconfigure_entry.data[CONF_FAMILY_ID]),
                )
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

    async def _async_authenticate_input(self, user_input: Mapping[str, Any]) -> dict[str, Any]:
        base_url = normalize_base_url(str(user_input[CONF_BASE_URL]))
        username = str(user_input[CONF_USERNAME]).strip()
        password = str(user_input[CONF_PASSWORD])

        session = async_get_clientsession(self.hass)
        client = HomeQuestsClient(session, base_url, username, password)
        context = await client.async_get_setup_context()
        return {
            "base_url": base_url,
            "username": username,
            "password": password,
            "me": context["me"],
            "families": context["families"],
        }

    async def _async_validate_input(
        self,
        user_input: Mapping[str, Any],
        *,
        expected_family_id: int | None = None,
    ) -> dict[str, Any]:
        context = await self._async_authenticate_input(user_input)
        families = context["families"]
        if not families:
            raise HomeQuestsNoFamilyError("No family available for configured user")
        if expected_family_id is None:
            family_id = int(families[0]["id"])
        else:
            family_id = int(expected_family_id)
        return self._build_entry_info(context, family_id)

    def _build_entry_info(self, setup_context: Mapping[str, Any], family_id: int) -> dict[str, Any]:
        families: list[dict[str, Any]] = list(setup_context["families"])
        family = next((entry for entry in families if int(entry["id"]) == family_id), None)
        if family is None:
            raise HomeQuestsNoFamilyError(f"Family {family_id} not available for configured user")

        base_url = str(setup_context["base_url"])
        username = str(setup_context["username"])
        password = str(setup_context["password"])
        me = setup_context["me"]
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
