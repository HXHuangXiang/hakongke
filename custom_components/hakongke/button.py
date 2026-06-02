"""Button platform for learned Konke remote commands."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    BUTTON_GROUP,
    BUTTON_NAME,
    BUTTON_SLOT,
    BUTTON_TYPE,
    CONF_REMOTE_BUTTONS,
    DATA_DEVICE,
    DATA_MODEL,
    DATA_NAME,
    DATA_REMOTE_BUTTON_ENTITIES,
    DEFAULT_REMOTE_GROUP,
    DOMAIN,
    TYPE_IR,
    TYPE_RF,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up learned remote command buttons from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    buttons = entry.options.get(CONF_REMOTE_BUTTONS, [])
    entities = [
        KonkeRemoteButton(data[DATA_DEVICE], data[DATA_NAME], data[DATA_MODEL], entry.data[CONF_HOST], button)
        for button in buttons
        if _valid_button(button)
    ]
    data[DATA_REMOTE_BUTTON_ENTITIES].extend(entities)
    async_add_entities(entities)


def _valid_button(button: dict) -> bool:
    """Return whether a stored remote button has the required fields."""
    return (
        button.get(BUTTON_TYPE) in (TYPE_IR, TYPE_RF)
        and isinstance(button.get(BUTTON_SLOT), int)
        and isinstance(button.get(BUTTON_NAME), str)
        and bool(button.get(BUTTON_NAME).strip())
    )


def _device_info(device, name: str, model: str, host: str) -> dict:
    """Return shared device info."""
    identifier = device.mac or f"{host}:{model}"
    return {
        "identifiers": {(DOMAIN, identifier)},
        "manufacturer": "Konke",
        "model": model,
        "name": name,
    }


class KonkeRemoteButton(ButtonEntity):
    """Button that sends a learned Konke IR/RF command."""

    _attr_has_entity_name = True

    def __init__(self, device, device_name: str, model: str, host: str, button: dict) -> None:
        """Initialize a learned remote button."""
        self._device = device
        self._remote_type = button[BUTTON_TYPE]
        self._group = button.get(BUTTON_GROUP) or DEFAULT_REMOTE_GROUP
        self._slot = button[BUTTON_SLOT]
        self._attr_name = button[BUTTON_NAME].strip()
        identifier = device.mac or f"{host}:{model}"
        suffix = f"{self._remote_type}:button:{self._slot}"
        if self._group != DEFAULT_REMOTE_GROUP:
            suffix = f"{self._remote_type}:button:{self._group}:{self._slot}"
        self._attr_unique_id = f"{identifier}:{suffix}"
        self._attr_device_info = _device_info(device, device_name, model, host)

    @property
    def remote_type(self) -> str:
        """Return the remote type."""
        return self._remote_type

    @property
    def group(self) -> str:
        """Return the learned command group."""
        return self._group

    @property
    def slot(self) -> int:
        """Return the learned command slot."""
        return self._slot

    @property
    def available(self) -> bool:
        """Return True if the parent device can send this command."""
        if not self._device.is_online:
            return False
        if self._remote_type == TYPE_IR:
            return self._device.is_support_ir
        if self._remote_type == TYPE_RF:
            return self._device.is_support_rf
        return False

    async def async_press(self) -> None:
        """Send the learned remote command."""
        slot = str(self._slot)
        if self._remote_type == TYPE_IR:
            await self._device.ir_emit(slot, self._group)
        elif self._remote_type == TYPE_RF:
            await self._device.rf_emit(slot, self._group)
        _LOGGER.debug("Send %s remote button slot %s: %s", self._remote_type, slot, self.unique_id)
