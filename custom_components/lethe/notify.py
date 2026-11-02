"""Notify-Entity: erlaubt notify.send_message aus eigenen Automationen."""

from __future__ import annotations

from homeassistant.components.notify import NotifyEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LetheConfigEntry
from .api import LetheError
from .const import CONF_BOT_NAME, CONF_CHAT_ID, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LetheConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([LetheNotifyEntity(entry)])


class LetheNotifyEntity(NotifyEntity):
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, entry: LetheConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = f"{entry.data[CONF_CHAT_ID]}_notify"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.data[CONF_CHAT_ID])},
            name=entry.data.get(CONF_BOT_NAME) or "Lethe",
            manufacturer="Lethe",
            model="Bot",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        text = f"{title}\n{message}" if title else message
        try:
            await self._entry.runtime_data.send(self._entry, text)
        except LetheError as err:
            raise HomeAssistantError(f"Lethe-Nachricht fehlgeschlagen: {err}") from err
