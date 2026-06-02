"""Sensor platform for Konke devices."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_ENABLE_SWITCH,
    DATA_DEVICE,
    DATA_MODEL,
    DATA_NAME,
    DOMAIN,
    MODEL_K2,
    normalize_model,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Konke sensors from a config entry."""
    if not bool(entry.options.get(CONF_ENABLE_SWITCH, entry.data.get(CONF_ENABLE_SWITCH))):
        return

    data = hass.data[DOMAIN][entry.entry_id]
    if normalize_model(data[DATA_MODEL]) != MODEL_K2:
        return

    async_add_entities([KonkePowerSensor(data[DATA_DEVICE], data[DATA_NAME], data[DATA_MODEL], entry.data[CONF_HOST])])


def _device_info(device, name: str, model: str, host: str) -> dict:
    """Return shared device info."""
    identifier = device.mac or f"{host}:{model}"
    return {
        "identifiers": {(DOMAIN, identifier)},
        "manufacturer": "Konke",
        "model": model,
        "name": name,
    }


class KonkePowerSensor(SensorEntity):
    """K2 current power sensor."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "power"

    def __init__(self, device, name: str, model: str, host: str) -> None:
        """Initialize the sensor."""
        self._device = device
        self._attr_name = "Power"
        self._attr_unique_id = f"{device.mac or f'{host}:{model}'}:power"
        self._attr_device_info = _device_info(device, name, model, host)
        self._attr_native_value = None

    @property
    def available(self) -> bool:
        """Return True if sensor is available."""
        return self._device.is_online

    async def async_update(self) -> None:
        """Update power value."""
        from pykongke.error import DeviceOffline

        prev_available = self.available
        try:
            self._attr_native_value = float(await self._device.get_power())
        except DeviceOffline:
            if prev_available:
                _LOGGER.warning("Device is offline %s", self.entity_id)
