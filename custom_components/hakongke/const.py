"""Constants for the hakongke integration."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_NAME

DOMAIN = "hakongke"

CONF_MODEL = "model"
CONF_ENABLE_SWITCH = "enable_switch"
CONF_ENABLE_LIGHT = "enable_light"
CONF_ENABLE_IR_REMOTE = "enable_ir_remote"
CONF_ENABLE_RF_REMOTE = "enable_rf_remote"

DEFAULT_NAME = "hakongke"
DEFAULT_TIMEOUT = 10
DEFAULT_SLOT = 1001
SLOT_RANGE = {"min": 1000, "max": 999999}

MODEL_K1 = "k1"
MODEL_K2 = "k2"
MODEL_MINIK = "minik"
MODEL_MUL = "mul"
MODEL_MICMUL = "micmul"
MODEL_KLIGHT = "klight"
MODEL_KBULB = "kbulb"
MODEL_K2_LIGHT = "k2_light"

MODEL_ALIASES = {
    "smart plugin": MODEL_K1,
    "k1": MODEL_K1,
    "k2": MODEL_K2,
    "k2 pro": MODEL_K2,
    "minik": MODEL_MINIK,
    "minik pro": MODEL_MINIK,
    "mul": MODEL_MUL,
    "micmul": MODEL_MICMUL,
    "klight": MODEL_KLIGHT,
    "kbulb": MODEL_KBULB,
    "k2_light": MODEL_K2_LIGHT,
}

MODELS = sorted(MODEL_ALIASES)
SWITCH_MODELS = {MODEL_K1, MODEL_K2, MODEL_MINIK, MODEL_MUL, MODEL_MICMUL}
LIGHT_MODELS = {MODEL_KLIGHT, MODEL_KBULB, MODEL_K2_LIGHT}
REMOTE_MODELS = {MODEL_K2, MODEL_MINIK}

TYPE_IR = "ir"
TYPE_RF = "rf"

DATA_DEVICE = "device"
DATA_MODEL = CONF_MODEL
DATA_NAME = CONF_NAME
DATA_REMOTE_ENTITIES = "remote_entities"


def normalize_model(model: str) -> str:
    """Return the pykongke device model for a configured model alias."""
    return MODEL_ALIASES[model.lower()]


def pykongke_model(model: str) -> str:
    """Return the model name accepted by pykongke.manager.get_device."""
    normalized = normalize_model(model)
    if normalized == MODEL_K2_LIGHT:
        return MODEL_K2
    return normalized


def default_enabled(model: str) -> dict[str, bool]:
    """Return default entity families for a model."""
    normalized = normalize_model(model)
    return {
        CONF_ENABLE_SWITCH: normalized in SWITCH_MODELS,
        CONF_ENABLE_LIGHT: normalized in LIGHT_MODELS,
        CONF_ENABLE_IR_REMOTE: normalized in REMOTE_MODELS,
        CONF_ENABLE_RF_REMOTE: normalized == MODEL_K2,
    }


def entry_title(data: dict) -> str:
    """Return a config entry title."""
    return data.get(CONF_NAME) or data[CONF_HOST]
