"""hakongke Home Assistant integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, CONF_NAME, CONF_TIMEOUT, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    BUTTON_NAME,
    BUTTON_SLOT,
    BUTTON_TYPE,
    CONF_MODEL,
    CONF_REMOTE_BUTTONS,
    DATA_DEVICE,
    DATA_MODEL,
    DATA_NAME,
    DATA_REMOTE_ENTITIES,
    DEFAULT_SLOT,
    DEFAULT_TIMEOUT,
    DOMAIN,
    SLOT_RANGE,
    TYPE_IR,
    TYPE_RF,
    entry_title,
    pykongke_model,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SWITCH, Platform.LIGHT, Platform.REMOTE, Platform.SENSOR, Platform.BUTTON]

SERVICE_LEARN_IR_BUTTON = "learn_ir_button"
SERVICE_LEARN_RF_BUTTON = "learn_rf_button"

LEARN_BUTTON_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_NAME): cv.string,
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
    """Register friendly remote button learning services."""

    async def _handle_learning_service(call: ServiceCall) -> None:
        entity_id = call.data[ATTR_ENTITY_ID]
        name = call.data[CONF_NAME].strip()
        timeout = call.data[CONF_TIMEOUT]
        remote_type = TYPE_IR if call.service == SERVICE_LEARN_IR_BUTTON else TYPE_RF
        notification_id = f"{DOMAIN}_{remote_type}_learn_button"
        log_title = "hakongke 遥控学习"

        if not name:
            _notify(hass, log_title, "按键名称不能为空。", notification_id)
            return

        match = _find_remote_entity(hass, entity_id, remote_type)
        if match is None:
            _notify(
                hass,
                log_title,
                f"没有找到匹配的遥控实体：{entity_id}。请确认选择的是对应类型的红外或射频遥控实体。",
                notification_id,
            )
            _LOGGER.warning("No %s remote entity matched learning request: %s", remote_type, entity_id)
            return

        entry, entity = match
        buttons = list(entry.options.get(CONF_REMOTE_BUTTONS, []))
        slot = _remote_button_slot(buttons, remote_type, name)
        if slot > SLOT_RANGE["max"]:
            _notify(
                hass,
                log_title,
                "没有可用的遥控按键编号，请先整理已学习按键。",
                notification_id,
            )
            return

        _notify(
            hass,
            log_title,
            f"开始学习“{name}”。请在 {timeout} 秒内对着控客设备按下实体遥控器上的目标按键。",
            notification_id,
        )
        _LOGGER.info(
            "Start learning %s remote button '%s' on slot %s for entity: %s",
            remote_type,
            name,
            slot,
            entity_id,
        )

        result = await entity.async_learn(str(slot), timeout=timeout)
        if not result:
            _notify(
                hass,
                log_title,
                f"学习“{name}”失败。请确认设备在线，并在倒计时内按下实体遥控器按键。",
                notification_id,
            )
            _LOGGER.warning("Learn %s remote button failed on slot %s: %s", remote_type, slot, entity_id)
            return

        buttons = [
            button
            for button in buttons
            if not (button.get(BUTTON_TYPE) == remote_type and button.get(BUTTON_NAME) == name)
        ]
        buttons.append({BUTTON_TYPE: remote_type, BUTTON_SLOT: slot, BUTTON_NAME: name})
        options = {**entry.options, CONF_REMOTE_BUTTONS: buttons}
        hass.config_entries.async_update_entry(entry, options=options)
        _notify(
            hass,
            log_title,
            f"学习“{name}”成功，正在创建按钮实体。稍后可在实体列表中直接点击该按钮发送遥控命令。",
            notification_id,
        )
        _LOGGER.info("Learn %s remote button success on slot %s: %s", remote_type, slot, entity_id)

    if not hass.services.has_service(DOMAIN, SERVICE_LEARN_IR_BUTTON):
        hass.services.async_register(
            DOMAIN,
            SERVICE_LEARN_IR_BUTTON,
            _handle_learning_service,
            schema=LEARN_BUTTON_SCHEMA,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_LEARN_RF_BUTTON):
        hass.services.async_register(
            DOMAIN,
            SERVICE_LEARN_RF_BUTTON,
            _handle_learning_service,
            schema=LEARN_BUTTON_SCHEMA,
        )


def _find_remote_entity(hass: HomeAssistant, entity_id: str, remote_type: str) -> tuple[ConfigEntry, object] | None:
    """Return the config entry and remote entity matching a learning request."""
    for entry_id, entry_data in hass.data.get(DOMAIN, {}).items():
        for entity in entry_data.get(DATA_REMOTE_ENTITIES, []):
            if entity.entity_id == entity_id and entity.remote_type == remote_type:
                entry = hass.config_entries.async_get_entry(entry_id)
                if entry is None:
                    return None
                return entry, entity
    return None


def _remote_button_slot(buttons: list[dict], remote_type: str, name: str) -> int:
    """Return an existing same-name slot, or the next unused slot."""
    for button in buttons:
        if button.get(BUTTON_TYPE) == remote_type and button.get(BUTTON_NAME) == name:
            slot = button.get(BUTTON_SLOT)
            if isinstance(slot, int):
                return slot

    used_slots = {
        button.get(BUTTON_SLOT)
        for button in buttons
        if button.get(BUTTON_TYPE) == remote_type and isinstance(button.get(BUTTON_SLOT), int)
    }
    slot = DEFAULT_SLOT
    while slot in used_slots and slot <= SLOT_RANGE["max"]:
        slot += 1
    return slot


def _notify(hass: HomeAssistant, title: str, message: str, notification_id: str) -> None:
    """Create or replace a persistent notification."""
    hass.components.persistent_notification.async_create(
        message,
        title=title,
        notification_id=notification_id,
    )


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
