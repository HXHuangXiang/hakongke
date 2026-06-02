"""hakongke Home Assistant integration."""

from __future__ import annotations

import asyncio
import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.components.remote import ATTR_DELAY_SECS, ATTR_NUM_REPEATS
from homeassistant.components import persistent_notification
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, CONF_NAME, CONF_TIMEOUT, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    BUTTON_GROUP,
    BUTTON_NAME,
    BUTTON_SLOT,
    BUTTON_TYPE,
    CONF_MODEL,
    CONF_REMOTE_BUTTONS,
    DATA_DEVICE,
    DATA_MODEL,
    DATA_NAME,
    DATA_REMOTE_BUTTON_ENTITIES,
    DATA_REMOTE_ENTITIES,
    DEFAULT_REMOTE_GROUP,
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
SERVICE_CLEAR_IR_GROUP = "clear_ir_group"
SERVICE_DELETE_IR_BUTTON = "delete_ir_button"
SERVICE_SEND_IR_SLOT = "send_ir_slot"
SERVICE_ADD_IR_BUTTON = "add_ir_button"
CONF_GROUP = "group"
CONF_SLOT = "slot"

LEARN_BUTTON_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): vol.All(int, vol.Range(min=0)),
    }
)

CLEAR_GROUP_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_GROUP): cv.string,
    }
)

DELETE_BUTTON_SCHEMA = vol.Schema({vol.Required(ATTR_ENTITY_ID): cv.entity_id})

SEND_SLOT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_SLOT): vol.All(int, vol.Range(**SLOT_RANGE)),
        vol.Optional(CONF_GROUP, default=DEFAULT_REMOTE_GROUP): cv.string,
        vol.Optional(ATTR_NUM_REPEATS, default=1): vol.All(int, vol.Range(min=1)),
        vol.Optional(ATTR_DELAY_SECS, default=0.4): vol.All(vol.Coerce(float), vol.Range(min=0)),
    }
)

ADD_BUTTON_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_SLOT): vol.All(int, vol.Range(**SLOT_RANGE)),
        vol.Optional(CONF_GROUP, default=DEFAULT_REMOTE_GROUP): cv.string,
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
        DATA_REMOTE_BUTTON_ENTITIES: [],
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
        group = DEFAULT_REMOTE_GROUP
        slot = _remote_button_slot(buttons, remote_type, group, name)
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

        result = await entity.async_learn(str(slot), group=group, timeout=timeout)
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
            if not (
                button.get(BUTTON_TYPE) == remote_type
                and _button_group(button) == group
                and button.get(BUTTON_NAME) == name
            )
        ]
        buttons.append({BUTTON_TYPE: remote_type, BUTTON_GROUP: group, BUTTON_SLOT: slot, BUTTON_NAME: name})
        if not _save_remote_buttons(hass, entry, buttons, log_title, notification_id):
            return
        _notify(
            hass,
            log_title,
            f"学习“{name}”成功，正在创建按钮实体。稍后可在实体列表中直接点击该按钮发送遥控命令。",
            notification_id,
        )
        _LOGGER.info("Learn %s remote button success on slot %s: %s", remote_type, slot, entity_id)

    async def _handle_clear_ir_group(call: ServiceCall) -> None:
        entity_id = call.data[ATTR_ENTITY_ID]
        group = call.data[CONF_GROUP].strip()
        notification_id = f"{DOMAIN}_clear_ir_group"
        log_title = "hakongke 红外清理"

        if not group:
            _notify(hass, log_title, "红外组不能为空。", notification_id)
            return

        match = _find_remote_entity(hass, entity_id, TYPE_IR)
        if match is None:
            _notify(
                hass,
                log_title,
                f"没有找到匹配的红外遥控实体：{entity_id}。",
                notification_id,
            )
            _LOGGER.warning("No IR remote entity matched clear group request: %s", entity_id)
            return

        entry, entity = match
        _notify(
            hass,
            log_title,
            f"开始清空该控客设备红外组“{group}”中的已学习按键。",
            notification_id,
        )
        result = await entity.async_remove_group(group)
        if result is False:
            _notify(
                hass,
                log_title,
                f"清空红外组“{group}”失败。请确认设备在线后重试。",
                notification_id,
            )
            _LOGGER.warning("Clear IR group failed: %s %s", entity_id, group)
            return

        buttons = [
            button
            for button in entry.options.get(CONF_REMOTE_BUTTONS, [])
            if not (button.get(BUTTON_TYPE) == TYPE_IR and _button_group(button) == group)
        ]
        if not _save_remote_buttons(hass, entry, buttons, log_title, notification_id):
            return
        _notify(
            hass,
            log_title,
            f"已清空该控客设备红外组“{group}”，并移除 Home Assistant 中该组保存的红外按钮。",
            notification_id,
        )
        _LOGGER.info("Clear IR group success: %s %s", entity_id, group)

    async def _handle_delete_ir_button(call: ServiceCall) -> None:
        entity_id = call.data[ATTR_ENTITY_ID]
        notification_id = f"{DOMAIN}_delete_ir_button"
        log_title = "hakongke 红外删除"

        match = _find_remote_button_entity(hass, entity_id, TYPE_IR)
        if match is None:
            _notify(
                hass,
                log_title,
                f"没有找到匹配的红外按钮实体：{entity_id}。",
                notification_id,
            )
            _LOGGER.warning("No IR button entity matched delete request: %s", entity_id)
            return

        entry, button_entity = match
        remote_match = _find_remote_entity_for_entry(hass, entry.entry_id, TYPE_IR)
        if remote_match is None:
            _notify(
                hass,
                log_title,
                "没有找到对应的红外遥控实体，无法删除设备里的红外按键。",
                notification_id,
            )
            _LOGGER.warning("No IR remote entity found for button delete: %s", entity_id)
            return

        group = button_entity.group
        slot = button_entity.slot
        remote_entity = remote_match
        result = await remote_entity.async_remove(str(slot), group)
        if result is False:
            _notify(
                hass,
                log_title,
                f"删除红外按键失败：group={group}, slot={slot}。请确认设备在线后重试。",
                notification_id,
            )
            _LOGGER.warning("Delete IR button failed: %s group=%s slot=%s", entity_id, group, slot)
            return

        buttons = [
            button
            for button in entry.options.get(CONF_REMOTE_BUTTONS, [])
            if not (
                button.get(BUTTON_TYPE) == TYPE_IR
                and _button_group(button) == group
                and button.get(BUTTON_SLOT) == slot
            )
        ]
        if not _save_remote_buttons(hass, entry, buttons, log_title, notification_id):
            return
        _notify(
            hass,
            log_title,
            f"已删除红外按键：group={group}, slot={slot}，并移除对应按钮实体。",
            notification_id,
        )
        _LOGGER.info("Delete IR button success: %s group=%s slot=%s", entity_id, group, slot)

    async def _handle_send_ir_slot(call: ServiceCall) -> None:
        entity_id = call.data[ATTR_ENTITY_ID]
        group = call.data[CONF_GROUP].strip() or DEFAULT_REMOTE_GROUP
        slot = call.data[CONF_SLOT]
        num_repeats = call.data[ATTR_NUM_REPEATS]
        delay = call.data[ATTR_DELAY_SECS]
        notification_id = f"{DOMAIN}_send_ir_slot"
        log_title = "hakongke 红外发送"

        match = _find_remote_entity(hass, entity_id, TYPE_IR)
        if match is None:
            _notify(
                hass,
                log_title,
                f"没有找到匹配的红外遥控实体：{entity_id}。",
                notification_id,
            )
            _LOGGER.warning("No IR remote entity matched send slot request: %s", entity_id)
            return

        _, entity = match
        for repeat in range(num_repeats):
            if repeat > 0 and delay > 0:
                await asyncio.sleep(delay)
            await entity.async_emit(str(slot), group)

        _notify(
            hass,
            log_title,
            f"已发送红外命令：group={group}, slot={slot}。",
            notification_id,
        )
        _LOGGER.info("Send IR slot success: %s group=%s slot=%s", entity_id, group, slot)

    async def _handle_add_ir_button(call: ServiceCall) -> None:
        entity_id = call.data[ATTR_ENTITY_ID]
        name = call.data[CONF_NAME].strip()
        group = call.data[CONF_GROUP].strip() or DEFAULT_REMOTE_GROUP
        slot = call.data[CONF_SLOT]
        notification_id = f"{DOMAIN}_add_ir_button"
        log_title = "hakongke 红外按钮"

        if not name:
            _notify(hass, log_title, "按键名称不能为空。", notification_id)
            return

        match = _find_remote_entity(hass, entity_id, TYPE_IR)
        if match is None:
            _notify(
                hass,
                log_title,
                f"没有找到匹配的红外遥控实体：{entity_id}。",
                notification_id,
            )
            _LOGGER.warning("No IR remote entity matched add button request: %s", entity_id)
            return

        entry, _ = match
        buttons = [
            button
            for button in entry.options.get(CONF_REMOTE_BUTTONS, [])
            if not (
                button.get(BUTTON_TYPE) == TYPE_IR
                and _button_group(button) == group
                and button.get(BUTTON_SLOT) == slot
            )
        ]
        buttons.append({BUTTON_TYPE: TYPE_IR, BUTTON_GROUP: group, BUTTON_SLOT: slot, BUTTON_NAME: name})
        if not _save_remote_buttons(hass, entry, buttons, log_title, notification_id):
            return
        _notify(
            hass,
            log_title,
            f"已保存红外按钮“{name}”：group={group}, slot={slot}。",
            notification_id,
        )
        _LOGGER.info("Add IR button success: %s group=%s slot=%s name=%s", entity_id, group, slot, name)

    if not hass.services.has_service(DOMAIN, SERVICE_LEARN_IR_BUTTON):
        hass.services.async_register(
            DOMAIN,
            SERVICE_LEARN_IR_BUTTON,
            _handle_learning_service,
            schema=LEARN_BUTTON_SCHEMA,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_CLEAR_IR_GROUP):
        hass.services.async_register(
            DOMAIN,
            SERVICE_CLEAR_IR_GROUP,
            _handle_clear_ir_group,
            schema=CLEAR_GROUP_SCHEMA,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_DELETE_IR_BUTTON):
        hass.services.async_register(
            DOMAIN,
            SERVICE_DELETE_IR_BUTTON,
            _handle_delete_ir_button,
            schema=DELETE_BUTTON_SCHEMA,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_SEND_IR_SLOT):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SEND_IR_SLOT,
            _handle_send_ir_slot,
            schema=SEND_SLOT_SCHEMA,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_ADD_IR_BUTTON):
        hass.services.async_register(
            DOMAIN,
            SERVICE_ADD_IR_BUTTON,
            _handle_add_ir_button,
            schema=ADD_BUTTON_SCHEMA,
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


def _find_remote_entity_for_entry(hass: HomeAssistant, entry_id: str, remote_type: str) -> object | None:
    """Return the remote entity for a config entry and remote type."""
    entry_data = hass.data.get(DOMAIN, {}).get(entry_id)
    if entry_data is None:
        return None
    for entity in entry_data.get(DATA_REMOTE_ENTITIES, []):
        if entity.remote_type == remote_type:
            return entity
    return None


def _find_remote_button_entity(hass: HomeAssistant, entity_id: str, remote_type: str) -> tuple[ConfigEntry, object] | None:
    """Return the config entry and learned remote button entity."""
    for entry_id, entry_data in hass.data.get(DOMAIN, {}).items():
        for entity in entry_data.get(DATA_REMOTE_BUTTON_ENTITIES, []):
            if entity.entity_id == entity_id and entity.remote_type == remote_type:
                entry = hass.config_entries.async_get_entry(entry_id)
                if entry is None:
                    return None
                return entry, entity
    return None


def _remote_button_slot(buttons: list[dict], remote_type: str, group: str, name: str) -> int:
    """Return an existing same-name slot, or the next unused slot."""
    for button in buttons:
        if (
            button.get(BUTTON_TYPE) == remote_type
            and _button_group(button) == group
            and button.get(BUTTON_NAME) == name
        ):
            slot = button.get(BUTTON_SLOT)
            if isinstance(slot, int):
                return slot

    used_slots = {
        button.get(BUTTON_SLOT)
        for button in buttons
        if button.get(BUTTON_TYPE) == remote_type
        and _button_group(button) == group
        and isinstance(button.get(BUTTON_SLOT), int)
    }
    slot = DEFAULT_SLOT
    while slot in used_slots and slot <= SLOT_RANGE["max"]:
        slot += 1
    return slot


def _button_group(button: dict) -> str:
    """Return a stored button group, defaulting old mappings to pykongke."""
    return button.get(BUTTON_GROUP) or DEFAULT_REMOTE_GROUP


def _save_remote_buttons(
    hass: HomeAssistant,
    entry: ConfigEntry,
    buttons: list[dict],
    title: str,
    notification_id: str,
) -> bool:
    """Persist learned button mappings."""
    options = {**entry.options, CONF_REMOTE_BUTTONS: buttons}
    try:
        hass.config_entries.async_update_entry(entry, options=options)
    except Exception as err:  # noqa: BLE001 - Home Assistant surfaces this as an unknown action error.
        _notify(hass, title, f"保存遥控按钮配置失败：{err}", notification_id)
        _LOGGER.exception("Failed to update hakongke remote button options")
        return False
    return True


def _notify(hass: HomeAssistant, title: str, message: str, notification_id: str) -> None:
    """Create or replace a persistent notification."""
    persistent_notification.async_create(hass, message, title=title, notification_id=notification_id)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload entry when options change."""
    task = hass.async_create_task(hass.config_entries.async_reload(entry.entry_id))

    def _log_reload_result(done_task: asyncio.Task) -> None:
        try:
            done_task.result()
        except Exception:  # noqa: BLE001 - keep options updates from surfacing as service failures.
            _LOGGER.exception("Failed to reload hakongke entry after options update")

    task.add_done_callback(_log_reload_result)
