"""Schlanker Client für die Lethe-Backend-API (Linked-Devices + Bot-API)."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote

import aiohttp


class LetheError(Exception):
    """Allgemeiner Fehler bei der Kommunikation mit Lethe."""


class LetheAuthError(LetheError):
    """Token ungültig oder abgelaufen."""


class LetheApi:
    """HTTP-Client. Nutzer-JWT wird nur während der Einrichtung verwendet,
    danach läuft alles über den Bot-Token (lth_bot_...)."""

    def __init__(self, session: aiohttp.ClientSession, base_url: str) -> None:
        self._session = session
        self._base = base_url.rstrip("/")

    async def _request(
        self,
        method: str,
        path: str,
        token: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        try:
            async with self._session.request(
                method,
                f"{self._base}{path}",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status in (401, 403):
                    raise LetheAuthError(f"HTTP {resp.status}")
                if resp.status >= 400:
                    raise LetheError(f"HTTP {resp.status}: {await resp.text()}")
                return await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            raise LetheError(str(err)) from err
        except TimeoutError as err:
            raise LetheError("Zeitüberschreitung") from err

    # --- QR-Login (gleicher Ablauf wie der Lethe-Webclient) ---

    async def init_qr(self) -> str:
        data = await self._request("POST", "/linked-devices/init-qr")
        return data["token"]

    def qr_image_url(self, qr_token: str) -> str:
        # Format, das die Android-App beim Scannen versteht: {"t": "<token>"}
        payload = quote(json.dumps({"t": qr_token}, separators=(",", ":")))
        return f"{self._base}/linked-devices/qr-image?data={payload}"

    async def check_qr(self, qr_token: str) -> dict[str, Any]:
        return await self._request("GET", f"/linked-devices/check/{qr_token}")

    async def unlink_device(self, jwt: str, device_id: str) -> None:
        await self._request("DELETE", f"/linked-devices/{device_id}", token=jwt)

    async def get_me(self, jwt: str) -> dict[str, Any]:
        return await self._request("GET", "/users/me", token=jwt)

    # --- Bot-API ---

    async def register_bot(self, jwt: str, name: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/bots/register",
            token=jwt,
            payload={"name": name, "description": "Benachrichtigungen aus Home Assistant"},
        )

    async def start_bot_chat(self, jwt: str, bot_fake_number: str) -> None:
        await self._request("POST", f"/bots/{bot_fake_number}/start", token=jwt)

    async def bot_me(self, bot_token: str) -> dict[str, Any]:
        return await self._request("GET", "/bots/me", token=bot_token)

    async def send_message(self, bot_token: str, chat_id: str, text: str) -> None:
        await self._request(
            "POST",
            "/bots/send",
            token=bot_token,
            payload={"chat_id": chat_id, "text": text, "media_type": "text"},
        )
