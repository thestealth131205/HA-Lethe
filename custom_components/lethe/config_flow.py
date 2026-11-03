"""Config- und Options-Flow für Lethe Messenger.

Einrichtung: URL + Bot-Name → QR-Code wird angezeigt → in der Lethe-App unter
„Verknüpfte Geräte“ scannen → Integration legt einen eigenen Bot an, startet den
Chat mit dir und verwirft danach die Login-Session wieder.

Optionen: Regeln „wenn Entity X Bedingung Y erfüllt → sende Nachricht Z“.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import LetheApi, LetheError
from .const import (
    CONF_BOT_FAKE_NUMBER,
    CONF_BOT_ID,
    CONF_BOT_NAME,
    CONF_BOT_TOKEN,
    CONF_CHAT_ID,
    CONF_COOLDOWN,
    CONF_DELETE,
    CONF_ENABLED,
    CONF_ENTITIES,
    CONF_MESSAGE,
    CONF_OPERATOR,
    CONF_RULE_ID,
    CONF_RULE_NAME,
    CONF_RULES,
    CONF_URL,
    CONF_USER_NAME,
    CONF_VALUE,
    DEFAULT_BOT_NAME,
    DEFAULT_MESSAGE,
    DEFAULT_URL,
    DOMAIN,
    OP_CHANGED,
    OPERATORS,
    QR_POLL_INTERVAL,
    QR_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


class QrExpired(Exception):
    """QR-Code wurde nicht rechtzeitig gescannt."""


class LetheConfigFlow(ConfigFlow, domain=DOMAIN):
    """Einrichtung per QR-Code aus der Lethe-App."""

    VERSION = 1

    def __init__(self) -> None:
        self._url = DEFAULT_URL
        self._bot_name = DEFAULT_BOT_NAME
        self._api: LetheApi | None = None
        self._qr_token: str | None = None
        self._link_task: asyncio.Task | None = None
        self._auth: dict[str, Any] | None = None
        self._reauth = False

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> LetheOptionsFlow:
        return LetheOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            self._url = user_input[CONF_URL].rstrip("/")
            self._bot_name = user_input[CONF_BOT_NAME].strip() or DEFAULT_BOT_NAME
            self._api = LetheApi(async_get_clientsession(self.hass), self._url)
            try:
                self._qr_token = await self._api.init_qr()
            except LetheError as err:
                _LOGGER.warning("Lethe nicht erreichbar: %s", err)
                errors["base"] = "cannot_connect"
            else:
                return await self.async_step_link()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_URL, default=self._url): str,
                    vol.Required(CONF_BOT_NAME, default=self._bot_name): str,
                }
            ),
            errors=errors,
        )

    async def _wait_for_scan(self) -> dict[str, Any]:
        assert self._api and self._qr_token
        deadline = time.monotonic() + QR_TIMEOUT
        while time.monotonic() < deadline:
            try:
                result = await self._api.check_qr(self._qr_token)
            except LetheError as err:
                _LOGGER.debug("QR-Status-Abfrage fehlgeschlagen: %s", err)
            else:
                status = result.get("status")
                if status == "authorized":
                    return result
                if status == "expired":
                    break
            await asyncio.sleep(QR_POLL_INTERVAL)
        raise QrExpired

    async def async_step_link(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._api and self._qr_token
        if self._link_task is None:
            self._link_task = self.hass.async_create_task(self._wait_for_scan())

        if not self._link_task.done():
            return self.async_show_progress(
                step_id="link",
                progress_action="wait_scan",
                progress_task=self._link_task,
                description_placeholders={
                    "qr_url": self._api.qr_image_url(self._qr_token)
                },
            )

        try:
            self._auth = self._link_task.result()
        except QrExpired:
            self._link_task = None
            return self.async_show_progress_done(next_step_id="expired")
        return self.async_show_progress_done(next_step_id="finish")

    async def async_step_expired(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """QR abgelaufen – auf Wunsch neuen Code erzeugen."""
        if user_input is not None:
            if self._reauth:
                return await self.async_step_reauth_confirm({})
            return await self.async_step_user(
                {CONF_URL: self._url, CONF_BOT_NAME: self._bot_name}
            )
        return self.async_show_form(step_id="expired", data_schema=vol.Schema({}))

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Wird aufgerufen, wenn der gespeicherte Bot-Token ungültig geworden ist."""
        self._reauth = True
        self._url = entry_data[CONF_URL]
        self._bot_name = entry_data[CONF_BOT_NAME]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Bestätigung, dann QR-Login wie bei der Erstanmeldung."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._api = LetheApi(async_get_clientsession(self.hass), self._url)
            try:
                self._qr_token = await self._api.init_qr()
            except LetheError as err:
                _LOGGER.warning("Lethe nicht erreichbar: %s", err)
                errors["base"] = "cannot_connect"
            else:
                return await self.async_step_link()

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({}),
            errors=errors,
            description_placeholders={"bot_name": self._bot_name},
        )

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._api and self._auth
        jwt = self._auth["jwt"]
        device_id = self._auth.get("device_id")
        try:
            me = await self._api.get_me(jwt)
            await self.async_set_unique_id(me["id"])
            if self._reauth:
                # Verhindert, dass ein QR-Code eines anderen Lethe-Accounts
                # den Bot-Token dieses bestehenden Eintrags übernimmt.
                self._abort_if_unique_id_mismatch(reason="wrong_account")
            else:
                self._abort_if_unique_id_configured()

            bot = await self._api.register_bot(jwt, self._bot_name)
            await self._api.start_bot_chat(jwt, bot["fake_number"])
            await self._api.send_message(
                bot["bot_token"],
                me["id"],
                "✅ Home Assistant ist jetzt mit Lethe verbunden.",
            )
        except LetheError as err:
            _LOGGER.error("Einrichtung bei Lethe fehlgeschlagen: %s", err)
            return self.async_abort(reason="setup_failed")
        finally:
            # Die Web-Session wird nur zur Einrichtung gebraucht – danach wieder abmelden,
            # damit sie nicht dauerhaft unter „Verknüpfte Geräte“ hängt.
            if device_id:
                try:
                    await self._api.unlink_device(jwt, device_id)
                except LetheError as err:
                    _LOGGER.debug("Abmelden der Einrichtungs-Session fehlgeschlagen: %s", err)

        data = {
            CONF_URL: self._url,
            CONF_BOT_NAME: self._bot_name,
            CONF_BOT_TOKEN: bot["bot_token"],
            CONF_BOT_ID: bot["id"],
            CONF_BOT_FAKE_NUMBER: bot["fake_number"],
            CONF_CHAT_ID: me["id"],
            CONF_USER_NAME: me.get("name", ""),
        }

        if self._reauth:
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data=data
            )

        return self.async_create_entry(
            title=f"Lethe ({me.get('name') or me.get('fake_number')})",
            data=data,
            options={CONF_RULES: []},
        )


OPERATOR_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=OPERATORS,
        translation_key="operator",
        mode=selector.SelectSelectorMode.DROPDOWN,
    )
)


def _rule_schema(rule: dict[str, Any] | None, with_delete: bool) -> vol.Schema:
    rule = rule or {}
    schema: dict[Any, Any] = {
        vol.Required(CONF_RULE_NAME, default=rule.get(CONF_RULE_NAME, "")): str,
        vol.Required(
            CONF_ENTITIES, default=rule.get(CONF_ENTITIES, [])
        ): selector.EntitySelector(selector.EntitySelectorConfig(multiple=True)),
        vol.Required(
            CONF_OPERATOR, default=rule.get(CONF_OPERATOR, "eq")
        ): OPERATOR_SELECTOR,
        vol.Optional(
            CONF_VALUE, description={"suggested_value": rule.get(CONF_VALUE, "on")}
        ): str,
        vol.Required(
            CONF_MESSAGE, default=rule.get(CONF_MESSAGE, DEFAULT_MESSAGE)
        ): selector.TextSelector(selector.TextSelectorConfig(multiline=True)),
        vol.Required(
            CONF_COOLDOWN, default=rule.get(CONF_COOLDOWN, 0)
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0, max=86400, step=1, unit_of_measurement="s",
                mode=selector.NumberSelectorMode.BOX,
            )
        ),
        vol.Required(CONF_ENABLED, default=rule.get(CONF_ENABLED, True)): bool,
    }
    if with_delete:
        schema[vol.Required(CONF_DELETE, default=False)] = bool
    return vol.Schema(schema)


def _validate_rule(user_input: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    if not user_input.get(CONF_ENTITIES):
        errors[CONF_ENTITIES] = "no_entities"
    op = user_input[CONF_OPERATOR]
    value = (user_input.get(CONF_VALUE) or "").strip()
    if op != OP_CHANGED and not value:
        errors[CONF_VALUE] = "value_required"
    if op in ("gt", "lt"):
        try:
            float(value.replace(",", "."))
        except ValueError:
            errors[CONF_VALUE] = "value_not_number"
    return errors


TPL_HELP = "`{{ name }}`, `{{ state }}`, `{{ old_state }}`, `{{ unit }}`, `{{ entity_id }}`"


class LetheOptionsFlow(OptionsFlow):
    """Regeln verwalten: hinzufügen, bearbeiten, löschen."""

    def __init__(self) -> None:
        self._rules: list[dict[str, Any]] | None = None
        self._edit_id: str | None = None

    @property
    def rules(self) -> list[dict[str, Any]]:
        if self._rules is None:
            self._rules = [dict(r) for r in self.config_entry.options.get(CONF_RULES, [])]
        return self._rules

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        menu = ["add_rule", "save"]
        if self.rules:
            menu.insert(1, "select_rule")
        return self.async_show_menu(
            step_id="init",
            menu_options=menu,
            description_placeholders={
                "rules": "\n".join(
                    f"- {'✅' if r.get(CONF_ENABLED, True) else '⏸️'} {r[CONF_RULE_NAME]}"
                    for r in self.rules
                )
                or "_Noch keine Regeln angelegt._"
            },
        )

    async def async_step_add_rule(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_rule(user_input)
            if not errors:
                self.rules.append(
                    {CONF_RULE_ID: uuid.uuid4().hex, **_clean(user_input)}
                )
                return await self.async_step_init()
        return self.async_show_form(
            step_id="add_rule",
            data_schema=self.add_suggested_values_to_schema(
                _rule_schema(None, with_delete=False), user_input or {}
            ),
            errors=errors,
            description_placeholders={"tpl_help": TPL_HELP},
        )

    async def async_step_select_rule(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._edit_id = user_input["rule"]
            return await self.async_step_edit_rule()
        return self.async_show_form(
            step_id="select_rule",
            data_schema=vol.Schema(
                {
                    vol.Required("rule"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=r[CONF_RULE_ID], label=r[CONF_RULE_NAME]
                                )
                                for r in self.rules
                            ]
                        )
                    )
                }
            ),
        )

    async def async_step_edit_rule(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        idx = next(
            i for i, r in enumerate(self.rules) if r[CONF_RULE_ID] == self._edit_id
        )
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input.get(CONF_DELETE):
                self.rules.pop(idx)
                return await self.async_step_init()
            errors = _validate_rule(user_input)
            if not errors:
                self.rules[idx] = {CONF_RULE_ID: self._edit_id, **_clean(user_input)}
                return await self.async_step_init()
        return self.async_show_form(
            step_id="edit_rule",
            data_schema=_rule_schema(self.rules[idx], with_delete=True),
            errors=errors,
            description_placeholders={
                "name": self.rules[idx][CONF_RULE_NAME],
                "tpl_help": TPL_HELP,
            },
        )

    async def async_step_save(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_create_entry(data={CONF_RULES: self.rules})


def _clean(user_input: dict[str, Any]) -> dict[str, Any]:
    data = {k: v for k, v in user_input.items() if k != CONF_DELETE}
    data[CONF_VALUE] = (data.get(CONF_VALUE) or "").strip()
    data[CONF_COOLDOWN] = int(data.get(CONF_COOLDOWN) or 0)
    return data
