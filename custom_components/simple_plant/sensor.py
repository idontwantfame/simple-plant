"""Sensor platform for simple_plant."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
)

from .const import DOMAIN

if TYPE_CHECKING:
    from datetime import date, datetime

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import Event, EventStateChangedData, HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import SimplePlantCoordinator


ENTITY_DESCRIPTIONS = (
    SensorEntityDescription(
        device_class=SensorDeviceClass.DATE,
        key="next_watering",
        translation_key="next_watering",
        icon="mdi:clipboard-text-clock",
    ),
)

COLOR_MAPPING = {"Today": "Goldenrod", "Late": "Tomato"}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    async_add_entities(
        SimplePlantSensor(hass, entry, entity_description)
        for entity_description in ENTITY_DESCRIPTIONS
    )


class SimplePlantSensor(SensorEntity):
    """simple_plant sensor class."""

    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor class."""
        super().__init__()
        self.entity_description = description
        self._fallback_value: date | None = None
        self._attr_native_value: date | None = None
        self.coordinator: SimplePlantCoordinator = hass.data[DOMAIN][entry.entry_id]

        device = self.coordinator.device

        self.entity_id = f"sensor.{DOMAIN}_{description.key}_{device}"
        self._attr_unique_id = f"{DOMAIN}_{description.key}_{device}"

        self._attr_extra_state_attributes = {
            "state_color": False,
        }

        # Set up device info
        self._attr_device_info = self.coordinator.device_info

    @property
    def device(self) -> str | None:
        """Return the device name."""
        return self.coordinator.device

    @property
    def native_value(self) -> date | None:
        """Return the next watering date."""
        return (
            self._fallback_value
            if self._attr_native_value is None
            else self._attr_native_value
        )

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        await super().async_added_to_hass()
        device = self.coordinator.device
        registry = er.async_get(self.hass)

        # Resolve current entity IDs from the registry so renamed entities
        # are handled correctly after a restart.
        for entity_id in filter(None, [
            registry.async_get_entity_id("date", DOMAIN, f"{DOMAIN}_last_watered_{device}"),
            registry.async_get_entity_id("number", DOMAIN, f"{DOMAIN}_days_between_waterings_{device}"),
        ]):
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass,
                    entity_id,
                    self._update_state,
                )
            )
        self.async_on_remove(
            async_track_time_change(
                self.hass,
                self._update_state,
                hour=0,
                minute=0,
                second=0,
            )
        )

        # Initial update
        await self._update_state()

    async def _update_state(
        self, _event: Event[EventStateChangedData] | datetime | None = None
    ) -> None:
        """Update the sensor state based on other entities."""
        dates = self.coordinator.get_dates()

        if not dates:
            return

        # Color
        today = dates["today"]
        next_watering = dates["next_watering"]

        color_key = "OK"
        if today == next_watering:
            color_key = "Today"
        if today > next_watering:
            color_key = "Late"

        if color_key in COLOR_MAPPING:
            self._attr_extra_state_attributes = {
                "state_color": True,
                "color": COLOR_MAPPING[color_key],
            }
        else:
            self._attr_extra_state_attributes = {"state_color": False}

        # Value
        self._attr_native_value = next_watering
        self.async_write_ha_state()
