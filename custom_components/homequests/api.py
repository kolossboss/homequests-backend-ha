from __future__ import annotations

import asyncio
import logging
from typing import Any
from urllib.parse import urljoin

from aiohttp import ClientError, ClientResponseError, ClientSession
from async_timeout import timeout

from .const import REQUEST_TIMEOUT

_LOGGER = logging.getLogger(__name__)


class HomeQuestsApiError(Exception):
    """Base exception for API failures."""


class HomeQuestsAuthError(HomeQuestsApiError):
    """Raised when authentication fails."""


class HomeQuestsConnectionError(HomeQuestsApiError):
    """Raised when the backend cannot be reached."""


class HomeQuestsNoFamilyError(HomeQuestsApiError):
    """Raised when the account is not linked to a family."""


class HomeQuestsClient:
    def __init__(
        self,
        session: ClientSession,
        base_url: str,
        username: str,
        password: str,
    ) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._username = username
        self._password = password
        self._token: str | None = None
        self._auth_lock = asyncio.Lock()

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def username(self) -> str:
        return self._username

    def update_credentials(self, *, base_url: str, username: str, password: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._username = username
        self._password = password
        self._token = None

    async def async_get_setup_context(self) -> dict[str, Any]:
        await self.async_login(force=True)
        me, families = await asyncio.gather(
            self.async_get_me(),
            self.async_get_families(),
        )
        if not families:
            raise HomeQuestsNoFamilyError("No family available for configured user")

        family = families[0]
        return {
            "me": me,
            "families": families,
            "family": family,
        }

    async def async_login(self, *, force: bool = False) -> str:
        async with self._auth_lock:
            if self._token is not None and not force:
                return self._token

            payload = {"login": self._username, "password": self._password}
            response = await self._raw_request("POST", "/auth/login", json_body=payload, auth_required=False)
            token = response.get("access_token")
            if not token:
                raise HomeQuestsAuthError("Login response did not contain an access token")
            self._token = str(token)
            return self._token

    async def async_get_me(self) -> dict[str, Any]:
        return await self._request("GET", "/auth/me")

    async def async_get_families(self) -> list[dict[str, Any]]:
        response = await self._request("GET", "/families/my")
        return list(response)

    async def async_get_members(self, family_id: int) -> list[dict[str, Any]]:
        response = await self._request("GET", f"/families/{family_id}/members")
        return list(response)

    async def async_get_tasks(self, family_id: int) -> list[dict[str, Any]]:
        response = await self._request("GET", f"/families/{family_id}/tasks")
        return list(response)

    async def async_get_special_task_templates(self, family_id: int) -> list[dict[str, Any]]:
        response = await self._request("GET", f"/families/{family_id}/special-tasks/templates")
        return list(response)

    async def async_get_rewards(self, family_id: int) -> list[dict[str, Any]]:
        response = await self._request("GET", f"/families/{family_id}/rewards")
        return list(response)

    async def async_get_redemptions(self, family_id: int) -> list[dict[str, Any]]:
        response = await self._request("GET", f"/families/{family_id}/redemptions")
        return list(response)

    async def async_get_points_balances(self, family_id: int) -> list[dict[str, Any]]:
        response = await self._request("GET", f"/families/{family_id}/points/balances")
        return list(response)

    async def async_get_upcoming_reminders(self, family_id: int, *, window_minutes: int) -> list[dict[str, Any]]:
        response = await self._request(
            "GET",
            f"/families/{family_id}/tasks/reminders/upcoming?window_minutes={window_minutes}",
        )
        return list(response)

    async def async_get_dashboard_snapshot(self, family_id: int, *, reminder_window_minutes: int) -> dict[str, Any]:
        me, members, tasks, templates, rewards, redemptions, balances, reminders = await asyncio.gather(
            self.async_get_me(),
            self.async_get_members(family_id),
            self.async_get_tasks(family_id),
            self.async_get_special_task_templates(family_id),
            self.async_get_rewards(family_id),
            self.async_get_redemptions(family_id),
            self.async_get_points_balances(family_id),
            self.async_get_upcoming_reminders(family_id, window_minutes=reminder_window_minutes),
        )
        return {
            "me": me,
            "members": members,
            "tasks": tasks,
            "special_task_templates": templates,
            "rewards": rewards,
            "redemptions": redemptions,
            "points_balances": balances,
            "upcoming_reminders": reminders,
        }

    async def async_review_task(self, task_id: int, decision: str, comment: str | None = None) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/tasks/{task_id}/review",
            json_body={"decision": decision, "comment": comment},
        )

    async def async_review_missed_task(self, task_id: int, action: str, comment: str | None = None) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/tasks/{task_id}/missed-review",
            json_body={"action": action, "comment": comment},
        )

    async def async_review_redemption(self, redemption_id: int, decision: str, comment: str | None = None) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/redemptions/{redemption_id}/review",
            json_body={"decision": decision, "comment": comment},
        )

    async def async_adjust_points(self, family_id: int, user_id: int, points_delta: int, description: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/families/{family_id}/points/adjust",
            json_body={"user_id": user_id, "points_delta": points_delta, "description": description},
        )

    async def async_submit_task(self, task_id: int, note: str | None = None) -> dict[str, Any]:
        return await self._request("POST", f"/tasks/{task_id}/submit", json_body={"note": note})

    async def async_report_task_missed(self, task_id: int) -> dict[str, Any]:
        return await self._request("POST", f"/tasks/{task_id}/report-missed")

    async def _request(self, method: str, path: str, *, json_body: dict[str, Any] | None = None) -> Any:
        if self._token is None:
            await self.async_login()

        try:
            return await self._raw_request(method, path, json_body=json_body, auth_required=True)
        except HomeQuestsAuthError:
            _LOGGER.debug("Token rejected by HomeQuests backend, retrying login")
            await self.async_login(force=True)
            return await self._raw_request(method, path, json_body=json_body, auth_required=True)

    async def _raw_request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        auth_required: bool,
    ) -> Any:
        headers: dict[str, str] = {"Accept": "application/json"}
        if auth_required:
            if self._token is None:
                raise HomeQuestsAuthError("No access token available")
            headers["Authorization"] = f"Bearer {self._token}"

        url = urljoin(f"{self._base_url}/", path.lstrip("/"))
        try:
            async with timeout(REQUEST_TIMEOUT):
                async with self._session.request(method, url, json=json_body, headers=headers) as response:
                    if response.status in {401, 403}:
                        detail = await _response_detail(response)
                        raise HomeQuestsAuthError(detail or "Authentication failed")
                    response.raise_for_status()
                    if response.content_type == "application/json":
                        return await response.json()
                    return await response.text()
        except HomeQuestsAuthError:
            raise
        except asyncio.TimeoutError as err:
            raise HomeQuestsConnectionError(f"Request to {url} timed out") from err
        except ClientResponseError as err:
            detail = ""
            if err.status == 404:
                detail = "Endpoint not found"
            raise HomeQuestsApiError(f"HTTP {err.status}: {detail or err.message}") from err
        except ClientError as err:
            raise HomeQuestsConnectionError(f"Could not reach {url}") from err


async def _response_detail(response) -> str | None:
    try:
        payload = await response.json()
    except Exception:  # pragma: no cover - defensive parsing
        try:
            text = await response.text()
        except Exception:  # pragma: no cover - defensive parsing
            return None
        return text or None

    if isinstance(payload, dict):
        detail = payload.get("detail")
        if detail is not None:
            return str(detail)
    return None
