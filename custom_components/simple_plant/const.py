"""Constants for simple_plant."""

from logging import Logger, getLogger

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import Platform

STORAGE_KEY = "simple_plant_data"

LOGGER: Logger = getLogger(__package__)

DOMAIN = "simple_plant"

STORAGE_DIR = "simple_plant"

MANUFACTURER = "Simple Plant"

HEALTH_OPTIONS = [
    "notset",
    "poor",
    "fair",
    "good",
    "verygood",
    "excellent",
]

IMAGES_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".webp": "image/webp",
    ".tiff": "image/tiff",
    ".svg": "image/svg+xml",
}

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.BINARY_SENSOR,
    Platform.DATE,
    Platform.IMAGE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
]

MONITORED_METRICS: dict[str, dict] = {
    "moisture": {
        "device_class": SensorDeviceClass.MOISTURE,
        "unit": "%",
        "has_max": True,
        "default_min": 20,
        "default_max": 60,
        "step": 1,
        "range_min": 0,
        "range_max": 100,
    },
    "temperature": {
        "device_class": SensorDeviceClass.TEMPERATURE,
        "unit": "°C",
        "has_max": True,
        "default_min": 10,
        "default_max": 35,
        "step": 0.5,
        "range_min": -50,
        "range_max": 80,
    },
    "illuminance": {
        "device_class": SensorDeviceClass.ILLUMINANCE,
        "unit": "lx",
        "has_max": False,
        "default_min": 1000,
        "default_max": None,
        "step": 100,
        "range_min": 0,
        "range_max": 150000,
    },
    "conductivity": {
        "device_class": SensorDeviceClass.CONDUCTIVITY,
        "unit": "µS/cm",
        "has_max": True,
        "default_min": 500,
        "default_max": 3000,
        "step": 50,
        "range_min": 0,
        "range_max": 10000,
    },
    "battery": {
        "device_class": SensorDeviceClass.BATTERY,
        "unit": "%",
        "has_max": False,
        "default_min": 20,
        "default_max": None,
        "step": 1,
        "range_min": 0,
        "range_max": 100,
    },
}
