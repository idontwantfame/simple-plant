"""Number platform for simple_plant."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import UnitOfTime

from .const import DOMAIN, LOGGER, MONITORED_METRICS

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import SimplePlantCoordinator


ENTITY_DESCRIPTIONS = (
    NumberEntityDescription(
        key="days_between_waterings",
        translation_key="days_between_waterings",
        device_class=NumberDeviceClass.DURATION,
        mode=NumberMode.BOX,
        icon="mdi:counter",
        native_step=1,
        native_unit_of_measurement=UnitOfTime.DAYS,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the number platform."""
    entities: list[SimplePlantNumber | SimplePlantThresholdNumber] = [
        SimplePlantNumber(hass, entry, description) for description in ENTITY_DESCRIPTIONS
    ]
    for metric, config in MONITORED_METRICS.items():
        if not entry.data.get(f"{metric}_sensor"):
            continue
        entities.append(SimplePlantThresholdNumber(hass, entry, metric, "min", config))
        if config["has_max"]:
            entities.append(SimplePlantThresholdNumber(hass, entry, metric, "max", config))
    async_add_entities(entities)


class SimplePlantNumber(NumberEntity):
    """simple_plant number class."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_native_min_value = 1
    _attr_native_max_value = 60
    _attr_native_step = 1

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        description: NumberEntityDescription,
    ) -> None:
        """Initialize the number class."""
        super().__init__()
        self.entity_description = description
        self.coordinator: SimplePlantCoordinator = hass.data[DOMAIN][entry.entry_id]

        device = self.coordinator.device

        self.entity_id = f"number.{DOMAIN}_{description.key}_{device}"
        self._attr_unique_id = f"{DOMAIN}_{description.key}_{device}"

        # set value
        self._fallback_value = entry.data.get("days_between_waterings")

        # Set up device info
        self._attr_device_info = self.coordinator.device_info

    @property
    def device(self) -> str | None:
        """Return the device name."""
        return self.coordinator.device

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        await super().async_added_to_hass()

        def warning(msg: str) -> None:
            LOGGER.warning("%s :%s", self.unique_id, msg)

        if self.coordinator.data is None:
            warning("Coordinator not ready at initialization")
            return
        data = self.coordinator.data.get(self.unique_id)
        if data is None:
            if self._fallback_value is None:
                warning("Initialization failed as _fallback_value is None")
                return
            await self.async_set_native_value(self._fallback_value)
            return
        await self.async_set_native_value(float(data))

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        self._attr_native_value = value
        self.async_write_ha_state()

        # Save to persistent storage
        if self.unique_id is not None:
            await self.coordinator.async_store_value(self.unique_id, str(value))


class SimplePlantThresholdNumber(NumberEntity):
    """Editable threshold (min or max) for a monitored metric."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        metric: str,
        bound: str,
        metric_config: dict,
    ) -> None:
        """Initialize the threshold number entity."""
        super().__init__()
        self.coordinator: SimplePlantCoordinator = hass.data[DOMAIN][entry.entry_id]
        device = self.coordinator.device

        key = f"{metric}_{bound}"
        self.entity_id = f"number.{DOMAIN}_{key}_{device}"
        self._attr_unique_id = f"{DOMAIN}_{key}_{device}"
        self._attr_translation_key = key

        self._attr_native_min_value = float(metric_config["range_min"])
        self._attr_native_max_value = float(metric_config["range_max"])
        self._attr_native_step = float(metric_config["step"])
        self._attr_native_unit_of_measurement = metric_config["unit"]

        self._fallback_value: float = float(
            entry.data.get(f"{metric}_{bound}", metric_config[f"default_{bound}"])
        )

        self._attr_device_info = self.coordinator.device_info

    @property
    def device(self) -> str | None:
        """Return the device name."""
        return self.coordinator.device

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        await super().async_added_to_hass()

        if self.coordinator.data is None:
            LOGGER.warning("%s: Coordinator not ready at initialization", self.unique_id)
            await self.async_set_native_value(self._fallback_value)
            return
        data = self.coordinator.data.get(self.unique_id)
        if data is None:
            await self.async_set_native_value(self._fallback_value)
            return
        await self.async_set_native_value(float(data))

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        self._attr_native_value = value
        self.async_write_ha_state()
        if self.unique_id is not None:
            await self.coordinator.async_store_value(self.unique_id, str(value))
