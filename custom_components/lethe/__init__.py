"""Lethe Messenger – Benachrichtigungen aus Home Assistant in den Lethe-Chat."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import LetheApi, LetheAuthError, LetheError
from .const import (
    ATTR_MESSAGE,
    CONF_BOT_TOKEN,
    CONF_CHAT_ID,
    CONF_RULES,
    CONF_URL,
    DOMAIN,
    SERVICE_SEND_MESSAGE,
)
from .rules import RuleEngine

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.NOTIFY]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass
class LetheData:
    api: LetheApi
    engine: RuleEngine

    async def send(self, entry: ConfigEntry, text: str) -> None:
        await self.api.send_message(
            entry.data[CONF_BOT_TOKEN], entry.data[CONF_CHAT_ID], text
        )


type LetheConfigEntry = ConfigEntry[LetheData]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    async def _send_service(call: ServiceCall) -> None:
        entries = hass.config_entries.async_loaded_entries(DOMAIN)
        if not entries:
            raise HomeAssistantError("Keine Lethe-Integration eingerichtet")
        for entry in entries:
            try:
                await entry.runtime_data.send(entry, call.data[ATTR_MESSAGE])
            except LetheError as err:
                raise HomeAssistantError(f"Lethe-Nachricht fehlgeschlagen: {err}") from err

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_MESSAGE,
        _send_service,
        schema=vol.Schema({vol.Required(ATTR_MESSAGE): cv.string}),
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: LetheConfigEntry) -> bool:
    api = LetheApi(async_get_clientsession(hass), entry.data[CONF_URL])
    try:
        await api.bot_me(entry.data[CONF_BOT_TOKEN])
    except LetheAuthError as err:
        raise ConfigEntryAuthFailed("Bot-Token ungültig – Integration neu einrichten") from err
    except LetheError as err:
        raise ConfigEntryNotReady(str(err)) from err

    async def _send(text: str) -> None:
        try:
            await api.send_message(entry.data[CONF_BOT_TOKEN], entry.data[CONF_CHAT_ID], text)
        except LetheError as err:
            _LOGGER.error("Lethe-Nachricht konnte nicht gesendet werden: %s", err)

    engine = RuleEngine(hass, entry.options.get(CONF_RULES, []), _send)
    entry.runtime_data = LetheData(api=api, engine=engine)
    engine.start()
    entry.async_on_unload(engine.stop)
    entry.async_on_unload(entry.add_update_listener(_async_reload))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_reload(hass: HomeAssistant, entry: LetheConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: LetheConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
