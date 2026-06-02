"""Remote platform for Konke IR/RF devices."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable

import voluptuous as vol

from homeassistant.components.remote import (
    ATTR_DELAY_SECS,
    ATTR_NUM_REPEATS,
    DEFAULT_DELAY_SECS,
    PLATFORM_SCHEMA,
    RemoteEntity,
    RemoteEntityFeature,
)
from homeassistant.config_entries import ConfigEntry, SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_TIMEOUT, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    CONF_ENABLE_IR_REMOTE,
    CONF_ENABLE_LIGHT,
    CONF_ENABLE_RF_REMOTE,
    CONF_ENABLE_SWITCH,
    CONF_MODEL,
    DATA_DEVICE,
    DATA_MODEL,
    DATA_NAME,
    DATA_REMOTE_ENTITIES,
    DEFAULT_TIMEOUT,
    DOMAIN,
    MODEL_MINIK,
    REMOTE_MODELS,
    TYPE_IR,
    TYPE_RF,
    normalize_model,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "hakongke Remote"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_TYPE, default=TYPE_IR): vol.In((TYPE_IR, TYPE_RF)),
        vol.Required(CONF_MODEL, default=MODEL_MINIK): cv.string,
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> bool:
    """Import legacy YAML remote configuration."""
    remote_type = config[CONF_TYPE]
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_HOST: config[CONF_HOST],
                CONF_NAME: config[CONF_NAME],
                CONF_MODEL: config[CONF_MODEL],
                CONF_ENABLE_SWITCH: False,
                CONF_ENABLE_LIGHT: False,
                CONF_ENABLE_IR_REMOTE: remote_type == TYPE_IR,
                CONF_ENABLE_RF_REMOTE: remote_type == TYPE_RF,
            },
        )
    )
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Konke remotes from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    model = data[DATA_MODEL]
    if normalize_model(model) not in REMOTE_MODELS:
        return

    entities: list[KonkeRemote] = []
    if _entry_enabled(entry, CONF_ENABLE_IR_REMOTE):
        entities.append(KonkeRemote(data[DATA_DEVICE], data[DATA_NAME], model, entry.data[CONF_HOST], TYPE_IR))
    if _entry_enabled(entry, CONF_ENABLE_RF_REMOTE):
        entities.append(KonkeRemote(data[DATA_DEVICE], data[DATA_NAME], model, entry.data[CONF_HOST], TYPE_RF))

    data[DATA_REMOTE_ENTITIES].extend(entities)
    async_add_entities(entities)


def _entry_enabled(entry: ConfigEntry, key: str) -> bool:
    """Return whether an entity family is enabled."""
    return bool(entry.options.get(key, entry.data.get(key)))


def _device_info(device, name: str, model: str, host: str) -> dict:
    """Return shared device info."""
    identifier = device.mac or f"{host}:{model}"
    return {
        "identifiers": {(DOMAIN, identifier)},
        "manufacturer": "Konke",
        "model": model,
        "name": name,
    }


class KonkeRemote(RemoteEntity):
    """Konke IR/RF remote."""

    _attr_has_entity_name = True
    _attr_supported_features = RemoteEntityFeature.LEARN_COMMAND | RemoteEntityFeature.DELETE_COMMAND

    def __init__(self, device, name: str, model: str, host: str, remote_type: str) -> None:
        """Initialize the remote."""
        self._device = device
        self._remote_type = remote_type
        self._attr_name = remote_type.upper()
        self._attr_unique_id = f"{device.mac or f'{host}:{model}'}:{remote_type}"
        self._attr_device_info = _device_info(device, name, model, host)

    @property
    def remote_type(self) -> str:
        """Return the remote type."""
        return self._remote_type

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if not self._device.is_online:
            return False
        if self._remote_type == TYPE_IR:
            return self._device.is_support_ir
        if self._remote_type == TYPE_RF:
            return self._device.is_support_rf
        return False

    @property
    def is_on(self) -> bool:
        """Return False if device is unreachable, else True."""
        return self._device.is_online

    async def async_turn_on(self, **kwargs) -> None:
        """Remote does not support turn_on."""
        _LOGGER.error("Device does not support turn_on, please use remote.send_command.")

    async def async_turn_off(self, **kwargs) -> None:
        """Remote does not support turn_off."""
        _LOGGER.error("Device does not support turn_off, please use remote.send_command.")

    async def async_update(self) -> None:
        """Synchronize state with remote."""
        from pykongke.error import DeviceOffline

        prev_available = self.available
        try:
            await self._device.update()
        except DeviceOffline:
            if prev_available:
                _LOGGER.warning("Device is offline %s", self.entity_id)

    async def async_send_command(self, command: Iterable[str], **kwargs) -> None:
        """Send remote commands."""
        num_repeats = kwargs.get(ATTR_NUM_REPEATS) or 1
        delay = kwargs.get(ATTR_DELAY_SECS)
        if delay is None:
            delay = DEFAULT_DELAY_SECS
        commands = [command] if isinstance(command, str) else list(command)

        for _ in range(num_repeats):
            for item in commands:
                await self._do_send_command(item)
                await asyncio.sleep(delay)

    async def async_learn(self, command: str, timeout: int = DEFAULT_TIMEOUT) -> bool:
        """Learn a command using the legacy service."""
        if self._remote_type == TYPE_IR:
            return await self._device.ir_learn(command, timeout=timeout)
        if self._remote_type == TYPE_RF:
            return await self._device.rf_learn(command, timeout=timeout)
        return False

    async def async_learn_command(self, **kwargs) -> None:
        """Learn a command from Home Assistant's remote service."""
        command = kwargs.get("command")
        timeout = kwargs.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
        if isinstance(command, list):
            command = command[0] if command else None
        if command is None:
            _LOGGER.warning("Missing command for remote learning")
            return

        _, slot = self._parse_command(command)
        if slot is None:
            return
        await self.async_learn(slot, timeout=timeout)

    async def async_delete_command(self, command: Iterable[str], **kwargs) -> None:
        """Delete learned commands."""
        commands = [command] if isinstance(command, str) else list(command)
        for item in commands:
            command_type, slot = self._parse_command(item)
            if command_type != self._remote_type or slot is None:
                continue
            if self._remote_type == TYPE_IR:
                await self._device.ir_remove(slot)
            elif self._remote_type == TYPE_RF:
                await self._device.rf_remove(slot)

    async def _do_send_command(self, command: str) -> bool:
        """Send a single remote command."""
        command_type, slot = self._parse_command(command)
        if command_type != self._remote_type or slot is None:
            _LOGGER.warning("Illegal command type: %s", command)
            return False

        if self._remote_type == TYPE_IR:
            await self._device.ir_emit(slot)
        elif self._remote_type == TYPE_RF:
            await self._device.rf_emit(slot)
        return True

    @staticmethod
    def _parse_command(command: str) -> tuple[str | None, str | None]:
        """Parse command strings like ir_1001."""
        try:
            command_type, slot = command.split("_", 1)
        except ValueError:
            _LOGGER.warning("Illegal command format: %s", command)
            return None, None
        return command_type, slot
