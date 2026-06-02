"""Config flow for the hakongke integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_ENABLE_IR_REMOTE,
    CONF_ENABLE_LIGHT,
    CONF_ENABLE_RF_REMOTE,
    CONF_ENABLE_SWITCH,
    CONF_MODEL,
    DEFAULT_NAME,
    DOMAIN,
    MODELS,
    default_enabled,
    entry_title,
    normalize_model,
)


def _user_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Return the user config schema."""
    defaults = defaults or {}
    model = defaults.get(CONF_MODEL, "minik")
    enabled = default_enabled(model)
    enabled.update({key: defaults[key] for key in enabled if key in defaults})

    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): cv.string,
            vol.Optional(CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_NAME)): cv.string,
            vol.Required(CONF_MODEL, default=model): vol.In(MODELS),
            vol.Optional(CONF_ENABLE_SWITCH, default=enabled[CONF_ENABLE_SWITCH]): cv.boolean,
            vol.Optional(CONF_ENABLE_LIGHT, default=enabled[CONF_ENABLE_LIGHT]): cv.boolean,
            vol.Optional(CONF_ENABLE_IR_REMOTE, default=enabled[CONF_ENABLE_IR_REMOTE]): cv.boolean,
            vol.Optional(CONF_ENABLE_RF_REMOTE, default=enabled[CONF_ENABLE_RF_REMOTE]): cv.boolean,
        }
    )


def _options_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Return the options schema."""
    enabled = default_enabled(defaults[CONF_MODEL])
    enabled.update({key: defaults[key] for key in enabled if key in defaults})
    return vol.Schema(
        {
            vol.Optional(CONF_ENABLE_SWITCH, default=enabled[CONF_ENABLE_SWITCH]): cv.boolean,
            vol.Optional(CONF_ENABLE_LIGHT, default=enabled[CONF_ENABLE_LIGHT]): cv.boolean,
            vol.Optional(CONF_ENABLE_IR_REMOTE, default=enabled[CONF_ENABLE_IR_REMOTE]): cv.boolean,
            vol.Optional(CONF_ENABLE_RF_REMOTE, default=enabled[CONF_ENABLE_RF_REMOTE]): cv.boolean,
        }
    )


class KonkeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a hakongke config flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=_user_schema())

        data = self._normalize_input(user_input)
        await self.async_set_unique_id(self._unique_id(data))
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=entry_title(data), data=data)

    async def async_step_import(self, import_data: dict[str, Any]) -> FlowResult:
        """Import a legacy YAML platform configuration."""
        data = self._normalize_input(import_data)
        unique_id = self._unique_id(data)
        await self.async_set_unique_id(unique_id)

        existing = self._entry_for_unique_id(unique_id)
        if existing is not None:
            merged = dict(existing.data)
            for key in (
                CONF_ENABLE_SWITCH,
                CONF_ENABLE_LIGHT,
                CONF_ENABLE_IR_REMOTE,
                CONF_ENABLE_RF_REMOTE,
            ):
                merged[key] = bool(existing.data.get(key)) or bool(data.get(key))
            self.hass.config_entries.async_update_entry(existing, data=merged)
            await self.hass.config_entries.async_reload(existing.entry_id)
            return self.async_abort(reason="already_configured")

        return self.async_create_entry(title=entry_title(data), data=data)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Return the options flow."""
        return KonkeOptionsFlow()

    def _entry_for_unique_id(self, unique_id: str) -> config_entries.ConfigEntry | None:
        """Return an existing entry matching unique_id."""
        for entry in self._async_current_entries():
            if entry.unique_id == unique_id:
                return entry
        return None

    @staticmethod
    def _normalize_input(data: dict[str, Any]) -> dict[str, Any]:
        """Normalize flow input data."""
        model = normalize_model(data[CONF_MODEL])
        enabled = default_enabled(model)
        return {
            CONF_HOST: data[CONF_HOST],
            CONF_NAME: data.get(CONF_NAME) or DEFAULT_NAME,
            CONF_MODEL: model,
            CONF_ENABLE_SWITCH: data.get(CONF_ENABLE_SWITCH, enabled[CONF_ENABLE_SWITCH]),
            CONF_ENABLE_LIGHT: data.get(CONF_ENABLE_LIGHT, enabled[CONF_ENABLE_LIGHT]),
            CONF_ENABLE_IR_REMOTE: data.get(CONF_ENABLE_IR_REMOTE, enabled[CONF_ENABLE_IR_REMOTE]),
            CONF_ENABLE_RF_REMOTE: data.get(CONF_ENABLE_RF_REMOTE, enabled[CONF_ENABLE_RF_REMOTE]),
        }

    @staticmethod
    def _unique_id(data: dict[str, Any]) -> str:
        """Return the unique ID for a config entry."""
        return f"{data[CONF_HOST]}:{data[CONF_MODEL]}"


class KonkeOptionsFlow(config_entries.OptionsFlow):
    """Handle hakongke options."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Manage entity family options."""
        if user_input is None:
            current = {**self.config_entry.data, **self.config_entry.options}
            return self.async_show_form(step_id="init", data_schema=_options_schema(current))

        return self.async_create_entry(
            title="",
            data={
                CONF_ENABLE_SWITCH: user_input[CONF_ENABLE_SWITCH],
                CONF_ENABLE_LIGHT: user_input[CONF_ENABLE_LIGHT],
                CONF_ENABLE_IR_REMOTE: user_input[CONF_ENABLE_IR_REMOTE],
                CONF_ENABLE_RF_REMOTE: user_input[CONF_ENABLE_RF_REMOTE],
            },
        )
