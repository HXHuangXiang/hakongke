"""Light platform for Konke devices."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
    PLATFORM_SCHEMA,
)
from homeassistant.config_entries import ConfigEntry, SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.color import color_RGB_to_hs as rgb_to_hs
from homeassistant.util.color import color_hs_to_RGB as hs_to_rgb

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
    LIGHT_MODELS,
    MODEL_K2_LIGHT,
    MODEL_KBULB,
    MODEL_KLIGHT,
    normalize_model,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "hakongke Light"
KBULB_MIN_KELVIN = 2700
KBULB_MAX_KELVIN = 6493

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_MODEL): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> bool:
    """Import legacy YAML light configuration."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_HOST: config[CONF_HOST],
                CONF_NAME: config[CONF_NAME],
                CONF_MODEL: config[CONF_MODEL],
                CONF_ENABLE_SWITCH: False,
                CONF_ENABLE_LIGHT: True,
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
    """Set up Konke lights from a config entry."""
    if not _entry_enabled(entry, CONF_ENABLE_LIGHT):
        return

    data = hass.data[DOMAIN][entry.entry_id]
    model = data[DATA_MODEL]
    if normalize_model(model) not in LIGHT_MODELS:
        return

    async_add_entities(
        [
            KonkeLight(
                data[DATA_DEVICE],
                data[DATA_NAME],
                model,
                entry.data[CONF_HOST],
            )
        ]
    )


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


class KonkeLight(LightEntity):
    """Konke light device."""

    _attr_has_entity_name = True

    def __init__(self, device, name: str, model: str, host: str) -> None:
        """Initialize a Konke light."""
        self._device = device
        self._model = normalize_model(model)
        self._attr_name = None
        suffix = ":light" if self._model == MODEL_K2_LIGHT else ""
        self._attr_unique_id = f"{device.mac or f'{host}:{model}'}{suffix}"
        self._attr_device_info = _device_info(device, name, model, host)

        if self._model == MODEL_KBULB:
            self._attr_supported_color_modes = {ColorMode.COLOR_TEMP}
            self._attr_min_color_temp_kelvin = KBULB_MIN_KELVIN
            self._attr_max_color_temp_kelvin = KBULB_MAX_KELVIN
        elif self._model == MODEL_KLIGHT:
            self._attr_supported_color_modes = {ColorMode.HS}
        else:
            self._attr_supported_color_modes = {ColorMode.ONOFF}

    @property
    def available(self) -> bool:
        """Return True if light is available."""
        return self._device.is_online

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        if self._model == MODEL_K2_LIGHT:
            return self._device.light_status == "open"
        return self._device.status == "open"

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light."""
        if self._model not in (MODEL_KBULB, MODEL_KLIGHT):
            return None
        return round(self._device.brightness / 100 * 255)

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the HS color value."""
        if self._model != MODEL_KLIGHT:
            return None
        return rgb_to_hs(*self._device.color)

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature in Kelvin."""
        if self._model != MODEL_KBULB:
            return None
        return self._device.ct

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on the light."""
        _LOGGER.debug("Turn on light %s %s", self._device.ip, kwargs)
        if not self.is_on:
            if self._model == MODEL_K2_LIGHT:
                await self._device.turn_on_light()
            else:
                await self._device.turn_on()

        if (
            self._model in (MODEL_KBULB, MODEL_KLIGHT)
            and ATTR_BRIGHTNESS in kwargs
            and self.brightness != kwargs[ATTR_BRIGHTNESS]
        ):
            await self._device.set_brightness(round(kwargs[ATTR_BRIGHTNESS] * 100 / 255))

        if (
            self._model == MODEL_KBULB
            and ATTR_COLOR_TEMP_KELVIN in kwargs
            and self.color_temp_kelvin != kwargs[ATTR_COLOR_TEMP_KELVIN]
        ):
            await self._device.set_ct(kwargs[ATTR_COLOR_TEMP_KELVIN])

        if self._model == MODEL_KLIGHT and ATTR_HS_COLOR in kwargs and self.hs_color != kwargs[ATTR_HS_COLOR]:
            await self._device.set_color(*hs_to_rgb(*kwargs[ATTR_HS_COLOR]))

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the light."""
        if self._model == MODEL_K2_LIGHT:
            await self._device.turn_off_light()
        else:
            await self._device.turn_off()
        _LOGGER.debug("Turn off light %s", self._device.ip)

    async def async_update(self) -> None:
        """Synchronize state with light."""
        from pykongke.error import DeviceOffline

        prev_available = self.available
        try:
            await self._device.update(type="light")
        except DeviceOffline:
            if prev_available:
                _LOGGER.warning("Device is offline %s", self.entity_id)
