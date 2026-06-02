"""Switch platform for Konke devices."""

from __future__ import annotations

import logging
import time

import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.config_entries import ConfigEntry, SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_NAME
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
    DOMAIN,
    MODEL_MINIK,
    SWITCH_MODELS,
    normalize_model,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "hakongke Outlet"
UPDATE_DEBOUNCE = 0.3

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MODEL, default=MODEL_MINIK): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> bool:
    """Import legacy YAML switch configuration."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_HOST: config[CONF_HOST],
                CONF_NAME: config[CONF_NAME],
                CONF_MODEL: config[CONF_MODEL],
                CONF_ENABLE_SWITCH: True,
                CONF_ENABLE_LIGHT: False,
                CONF_ENABLE_IR_REMOTE: False,
                CONF_ENABLE_RF_REMOTE: False,
            },
        )
    )
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Konke switches from a config entry."""
    if not _entry_enabled(entry, CONF_ENABLE_SWITCH):
        return

    data = hass.data[DOMAIN][entry.entry_id]
    model = data[DATA_MODEL]
    if normalize_model(model) not in SWITCH_MODELS:
        return

    device = data[DATA_DEVICE]
    name = data[DATA_NAME]
    entities: list[SwitchEntity] = []

    if hasattr(device, "socket_count"):
        powerstrip = KonkePowerStrip(device, name, model, entry.data[CONF_HOST])
        for index in range(device.socket_count):
            entities.append(KonkePowerStripOutlet(powerstrip, index))
        for index in range(device.usb_count or 0):
            entities.append(KonkePowerStripUSB(powerstrip, index))
    else:
        entities.append(KonkeOutlet(name, device, model, entry.data[CONF_HOST]))
        if hasattr(device, "usb_status"):
            entities.append(KonkeUsbSwitch(name, device, model, entry.data[CONF_HOST]))

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


class KonkeOutlet(SwitchEntity):
    """Konke outlet switch."""

    _attr_has_entity_name = True
    _attr_translation_key = "outlet"

    def __init__(self, name: str, device, model: str, host: str) -> None:
        """Initialize the outlet."""
        self._device = device
        self._attr_name = None
        self._attr_unique_id = device.mac or f"{host}:{model}:relay"
        self._attr_device_info = _device_info(device, name, model, host)

    @property
    def available(self) -> bool:
        """Return True if outlet is available."""
        return self._device.is_online

    @property
    def is_on(self) -> bool:
        """Return true if outlet is on."""
        return self._device.status == "open"

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on the outlet."""
        await self._device.turn_on()
        _LOGGER.debug("Turn on outlet %s", self.unique_id)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the outlet."""
        await self._device.turn_off()
        _LOGGER.debug("Turn off outlet %s", self.unique_id)

    async def async_update(self) -> None:
        """Synchronize state with outlet."""
        from pykongke.error import DeviceOffline

        prev_available = self.available
        try:
            await self._device.update(type="relay")
        except DeviceOffline:
            if prev_available:
                _LOGGER.warning("Device is offline %s", self.entity_id)


class KonkeUsbSwitch(SwitchEntity):
    """Konke USB switch."""

    _attr_has_entity_name = True
    _attr_translation_key = "usb"

    def __init__(self, name: str, device, model: str, host: str) -> None:
        """Initialize the USB switch."""
        self._device = device
        self._attr_name = "USB"
        self._attr_unique_id = f"{device.mac or f'{host}:{model}'}:usb"
        self._attr_device_info = _device_info(device, name, model, host)

    @property
    def available(self) -> bool:
        """Return True if outlet is available."""
        return self._device.is_online

    @property
    def is_on(self) -> bool:
        """Return true if USB power is on."""
        return self._device.usb_status == "open"

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on USB power."""
        await self._device.turn_on_usb()
        _LOGGER.debug("Turn on USB %s", self.unique_id)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off USB power."""
        await self._device.turn_off_usb()
        _LOGGER.debug("Turn off USB %s", self.unique_id)

    async def async_update(self) -> None:
        """Synchronize state with outlet."""
        from pykongke.error import DeviceOffline

        prev_available = self.available
        try:
            await self._device.update(type="usb")
        except DeviceOffline:
            if prev_available:
                _LOGGER.warning("Device is offline %s", self.entity_id)


class KonkePowerStrip:
    """Shared power strip state."""

    def __init__(self, device, name: str, model: str, host: str) -> None:
        """Initialize the power strip."""
        self.name = name
        self.device = device
        self.model = model
        self.host = host
        self.last_update = 0.0

    @property
    def available(self) -> bool:
        """Return True if power strip is available."""
        return self.device.is_online

    @property
    def unique_id(self) -> str:
        """Return unique ID for the strip."""
        return self.device.mac or f"{self.host}:{self.model}"

    @property
    def device_info(self) -> dict:
        """Return shared device info."""
        return _device_info(self.device, self.name, self.model, self.host)

    def get_status(self, index: int) -> bool:
        """Return true if outlet is on."""
        return self.device.status[index] == "open"

    def get_usb_status(self, index: int) -> bool:
        """Return true if USB is on."""
        return self.device.usb_status[index] == "open"

    async def async_turn_on(self, index: int) -> None:
        """Turn on an outlet."""
        await self.device.turn_on(index)

    async def async_turn_off(self, index: int) -> None:
        """Turn off an outlet."""
        await self.device.turn_off(index)

    async def async_turn_on_usb(self, index: int) -> None:
        """Turn on USB."""
        await self.device.turn_on_usb(index)

    async def async_turn_off_usb(self, index: int) -> None:
        """Turn off USB."""
        await self.device.turn_off_usb(index)

    async def async_update(self) -> None:
        """Synchronize state with power strip."""
        from pykongke.error import DeviceOffline

        prev_available = self.available
        if time.time() - self.last_update < UPDATE_DEBOUNCE:
            return

        self.last_update = time.time()
        try:
            await self.device.update()
        except DeviceOffline:
            if prev_available:
                _LOGGER.warning("Device is offline %s", self.unique_id)


class KonkePowerStripOutlet(SwitchEntity):
    """Outlet in a Konke power strip."""

    _attr_has_entity_name = True

    def __init__(self, powerstrip: KonkePowerStrip, index: int) -> None:
        """Initialize the outlet."""
        self._powerstrip = powerstrip
        self._index = index
        self._attr_name = f"Outlet {index + 1}"
        self._attr_unique_id = f"{powerstrip.unique_id}:{index + 1}"
        self._attr_device_info = powerstrip.device_info

    @property
    def available(self) -> bool:
        """Return True if outlet is available."""
        return self._powerstrip.available

    @property
    def is_on(self) -> bool:
        """Return true if outlet is on."""
        return self._powerstrip.get_status(self._index)

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on the outlet."""
        await self._powerstrip.async_turn_on(self._index)
        _LOGGER.debug("Turn on outlet %s", self.unique_id)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the outlet."""
        await self._powerstrip.async_turn_off(self._index)
        _LOGGER.debug("Turn off outlet %s", self.unique_id)

    async def async_update(self) -> None:
        """Synchronize state with power strip."""
        await self._powerstrip.async_update()


class KonkePowerStripUSB(SwitchEntity):
    """USB switch in a Konke power strip."""

    _attr_has_entity_name = True

    def __init__(self, powerstrip: KonkePowerStrip, index: int) -> None:
        """Initialize the USB switch."""
        self._powerstrip = powerstrip
        self._index = index
        self._attr_name = f"USB {index + 1}"
        self._attr_unique_id = f"{powerstrip.unique_id}:usb_{index + 1}"
        self._attr_device_info = powerstrip.device_info

    @property
    def available(self) -> bool:
        """Return True if outlet is available."""
        return self._powerstrip.available

    @property
    def is_on(self) -> bool:
        """Return true if USB is on."""
        return self._powerstrip.get_usb_status(self._index)

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on USB."""
        await self._powerstrip.async_turn_on_usb(self._index)
        _LOGGER.debug("Turn on USB %s", self.unique_id)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off USB."""
        await self._powerstrip.async_turn_off_usb(self._index)
        _LOGGER.debug("Turn off USB %s", self.unique_id)

    async def async_update(self) -> None:
        """Synchronize state with power strip."""
        await self._powerstrip.async_update()
