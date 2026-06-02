"""hakongke Home Assistant integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, CONF_TIMEOUT, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_MODEL,
    DATA_DEVICE,
    DATA_MODEL,
    DATA_NAME,
    DATA_REMOTE_ENTITIES,
    DEFAULT_TIMEOUT,
    DOMAIN,
    SLOT_RANGE,
    TYPE_IR,
    TYPE_RF,
    entry_title,
    pykongke_model,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SWITCH, Platform.LIGHT, Platform.REMOTE, Platform.SENSOR]

SERVICE_IR_LEARN = "ir_learn"
SERVICE_RF_LEARN = "rf_learn"
CONF_SLOT = "slot"

LEARN_COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required(CONF_SLOT): vol.All(int, vol.Range(**SLOT_RANGE)),
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): vol.All(int, vol.Range(min=0)),
    }
)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the hakongke integration."""
    hass.data.setdefault(DOMAIN, {})
    _register_learning_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up hakongke from a config entry."""
    from pykongke.manager import get_device

    hass.data.setdefault(DOMAIN, {})

    model = entry.data[CONF_MODEL]
    device = get_device(entry.data[CONF_HOST], pykongke_model(model))

    try:
        await device.update()
    except Exception as err:  # noqa: BLE001 - pykongke exposes several runtime errors.
        _LOGGER.debug("Initial update failed for %s: %s", entry_title(entry.data), err)

    hass.data[DOMAIN][entry.entry_id] = {
        DATA_DEVICE: device,
        DATA_MODEL: model,
        DATA_NAME: entry.data.get(DATA_NAME) or entry_title(entry.data),
        DATA_REMOTE_ENTITIES: [],
    }

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a hakongke config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


def _register_learning_services(hass: HomeAssistant) -> None:
    """Register remote learning services."""
    async def _handle_learning_service(call: ServiceCall) -> None:
        entity_ids = set(call.data[ATTR_ENTITY_ID])
        slot = str(call.data[CONF_SLOT])
        timeout = call.data[CONF_TIMEOUT]
        remote_type = TYPE_IR if call.service == SERVICE_IR_LEARN else TYPE_RF
        notification_id = f"{DOMAIN}_{remote_type}_learn_{slot}"
        log_title = f"hakongke {remote_type.upper()} remote"
        log_message = (
            f"Start learning {remote_type.upper()} remote command on slot {slot}. "
            "Press a button on the remote."
        )

        hass.components.persistent_notification.async_create(
            log_message,
            title=log_title,
            notification_id=notification_id,
        )
        _LOGGER.info(
            "Start learning %s remote command on slot %s for entities: %s",
            remote_type,
            slot,
            ", ".join(sorted(entity_ids)),
        )

        matched = False

        for entry_data in hass.data.get(DOMAIN, {}).values():
            for entity in entry_data.get(DATA_REMOTE_ENTITIES, []):
                if entity.entity_id not in entity_ids or entity.remote_type != remote_type:
                    continue
                matched = True
                result = await entity.async_learn(slot, timeout=timeout)
                if result:
                    message = f"Learned {remote_type.upper()} remote command on slot {slot}: {entity.entity_id}"
                    hass.components.persistent_notification.async_create(
                        message,
                        title=log_title,
                        notification_id=notification_id,
                    )
                    _LOGGER.info("Learn %s remote success on slot %s: %s", remote_type, slot, entity.entity_id)
                else:
                    message = f"Failed to learn {remote_type.upper()} remote command on slot {slot}: {entity.entity_id}"
                    hass.components.persistent_notification.async_create(
                        message,
                        title=log_title,
                        notification_id=notification_id,
                    )
                    _LOGGER.warning("Learn %s remote failed on slot %s: %s", remote_type, slot, entity.entity_id)

        if not matched:
            message = (
                f"No {remote_type.upper()} remote entity matched "
                f"{', '.join(sorted(entity_ids))}. "
                "Check the entity_id and remote type."
            )
            hass.components.persistent_notification.async_create(
                message,
                title=log_title,
                notification_id=notification_id,
            )
            _LOGGER.warning(
                "No %s remote entity matched learning request for entities: %s",
                remote_type,
                ", ".join(sorted(entity_ids)),
            )

    if not hass.services.has_service(DOMAIN, SERVICE_IR_LEARN):
        hass.services.async_register(DOMAIN, SERVICE_IR_LEARN, _handle_learning_service, schema=LEARN_COMMAND_SCHEMA)
    if not hass.services.has_service(DOMAIN, SERVICE_RF_LEARN):
        hass.services.async_register(DOMAIN, SERVICE_RF_LEARN, _handle_learning_service, schema=LEARN_COMMAND_SCHEMA)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
