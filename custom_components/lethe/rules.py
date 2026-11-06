"""Regel-Engine: beobachtet Entities und sendet bei erfüllter Bedingung eine Lethe-Nachricht.

Gesendet wird nur beim Übergang „Bedingung nicht erfüllt → erfüllt“ (bzw. bei
„changed“ bei jeder echten Zustandsänderung), damit Attribut-Updates nicht spammen.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import CALLBACK_TYPE, Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.template import Template

from .const import (
    CONF_AWAY_ONLY_ENTITY,
    CONF_COOLDOWN,
    CONF_ENABLED,
    CONF_ENTITIES,
    CONF_MESSAGE,
    CONF_OPERATOR,
    CONF_RULE_ID,
    CONF_RULE_NAME,
    CONF_VALUE,
    OP_CHANGED,
    OP_EQ,
    OP_GT,
    OP_LT,
    OP_NE,
)

_LOGGER = logging.getLogger(__name__)

_INVALID = (STATE_UNAVAILABLE, STATE_UNKNOWN)


def _to_float(value: str) -> float | None:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def condition_met(rule: dict[str, Any], state: State | None) -> bool:
    """Prüft die Bedingung einer Regel gegen einen Zustand (nicht für „changed“)."""
    if state is None:
        return False
    op = rule[CONF_OPERATOR]
    expected = str(rule.get(CONF_VALUE, "")).strip()
    current = state.state

    if op == OP_EQ:
        return current.lower() == expected.lower()
    if op == OP_NE:
        return current not in _INVALID and current.lower() != expected.lower()
    if op in (OP_GT, OP_LT):
        cur, exp = _to_float(current), _to_float(expected)
        if cur is None or exp is None:
            return False
        return cur > exp if op == OP_GT else cur < exp
    return False


class RuleEngine:
    """Verwaltet die State-Listener aller Regeln eines Config-Entries."""

    def __init__(
        self,
        hass: HomeAssistant,
        rules: list[dict[str, Any]],
        send: Callable[[str], Awaitable[None]],
    ) -> None:
        self.hass = hass
        self._rules = [r for r in rules if r.get(CONF_ENABLED, True) and r.get(CONF_ENTITIES)]
        self._send = send
        self._unsubs: list[CALLBACK_TYPE] = []
        self._last_sent: dict[tuple[str, str], float] = {}

    @callback
    def start(self) -> None:
        for rule in self._rules:
            self._unsubs.append(
                async_track_state_change_event(
                    self.hass, rule[CONF_ENTITIES], self._make_listener(rule)
                )
            )
        _LOGGER.debug("Lethe: %d Regel(n) aktiv", len(self._rules))

    @callback
    def stop(self) -> None:
        while self._unsubs:
            self._unsubs.pop()()

    def _is_home(self, rule: dict[str, Any]) -> bool:
        """True nur, wenn die konfigurierte Anwesenheits-Entity eindeutig „home“ meldet."""
        entity_id = rule.get(CONF_AWAY_ONLY_ENTITY)
        if not entity_id:
            return False
        state = self.hass.states.get(entity_id)
        return state is not None and state.state == "home"

    def _make_listener(self, rule: dict[str, Any]):
        @callback
        def _listener(event: Event[EventStateChangedData]) -> None:
            old: State | None = event.data["old_state"]
            new: State | None = event.data["new_state"]
            if new is None:
                return

            if rule[CONF_OPERATOR] == OP_CHANGED:
                if old is None or old.state == new.state:
                    return
                if old.state in _INVALID or new.state in _INVALID:
                    return
            elif not condition_met(rule, new) or condition_met(rule, old):
                return

            if self._is_home(rule):
                return

            key = (rule[CONF_RULE_ID], new.entity_id)
            cooldown = int(rule.get(CONF_COOLDOWN) or 0)
            now = time.monotonic()
            if cooldown and now - self._last_sent.get(key, -cooldown) < cooldown:
                return
            self._last_sent[key] = now

            self.hass.async_create_task(self._fire(rule, old, new))

        return _listener

    async def _fire(self, rule: dict[str, Any], old: State | None, new: State) -> None:
        variables = {
            "entity_id": new.entity_id,
            "name": new.name,
            "state": new.state,
            "old_state": old.state if old else None,
            "unit": new.attributes.get("unit_of_measurement", ""),
            "attributes": dict(new.attributes),
            "rule": rule[CONF_RULE_NAME],
        }
        try:
            text = Template(rule[CONF_MESSAGE], self.hass).async_render(
                variables, parse_result=False
            )
        except TemplateError as err:
            _LOGGER.error("Lethe-Regel '%s': Template-Fehler: %s", rule[CONF_RULE_NAME], err)
            text = rule[CONF_MESSAGE]
        await self._send(str(text))
