"""Binary sensor platform for simple_plant."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
)

from .const import DOMAIN, MONITORED_METRICS

if TYPE_CHECKING:
    from datetime import date, datetime

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import Event, EventStateChangedData, HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import SimplePlantCoordinator


class SimplePlantBinarySensor(BinarySensorEntity):
    """simple_plant binary_sensor base class."""

    _attr_has_entity_name = True
    _fallback_value: bool = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary_sensor class."""
        super().__init__()
        self.entity_description = description
        self.coordinator: SimplePlantCoordinator = hass.data[DOMAIN][entry.entry_id]

        self._attr_should_poll = True

        device = self.coordinator.device

        self._attr_native_value: bool | None = None

        self.entity_id = f"binary_sensor.{DOMAIN}_{description.key}_{device}"
        self._attr_unique_id = f"{DOMAIN}_{description.key}_{device}"

        # Set up device info
        self._attr_device_info = self.coordinator.device_info

    @property
    def is_on(self) -> bool:
        """Return true if the binary_sensor is on."""
        return (
            self._fallback_value
            if self._attr_native_value is None
            else self._attr_native_value
        )

    @property
    def device(self) -> str | None:
        """Return the device name."""
        return self.coordinator.device

    def get_dates(self) -> dict[str, date] | None:
        """Get dates from relevant device entity states."""
        return self.coordinator.get_dates()

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        device = self.coordinator.device
        registry = er.async_get(self.hass)

        # Subscribe to state changes, resolving current entity IDs from the registry
        # so renamed entities are handled correctly after a restart.
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
        self,
        _event: Event[EventStateChangedData] | datetime | None = None,
    ) -> None:
        """Update the binary sensor state based on other entities."""
        raise NotImplementedError


class SimplePlantTodo(SimplePlantBinarySensor):
    """simple_plant binary_sensor for todo."""

    _fallback_value = False

    async def _update_state(self, _event: Event | None = None) -> None:
        """Update the binary sensor state based on other entities."""
        dates = self.get_dates()

        if not dates:
            return

        self._attr_native_value = dates["today"] >= dates["next_watering"]
        self.async_write_ha_state()


class SimplePlantProblem(SimplePlantBinarySensor):
    """simple_plant binary_sensor for problem."""

    _fallback_value = False
    _attr_translation_key = "problem"

    async def _update_state(self, _event: Event | None = None) -> None:
        """Update the binary sensor state based on other entities."""
        dates = self.get_dates()

        if not dates:
            return

        self._attr_native_value = dates["today"] > dates["next_watering"]
        self.async_write_ha_state()


ENTITIES = [
    {
        "class": SimplePlantTodo,
        "description": BinarySensorEntityDescription(
            key="todo",
            translation_key="todo",
            name="Simple Plant Binary Sensor Todo",
            icon="mdi:water-check-outline",
        ),
    },
    {
        "class": SimplePlantProblem,
        "description": BinarySensorEntityDescription(
            key="problem",
            translation_key="problem",
            name="Simple Plant Binary Sensor Problem",
            device_class=BinarySensorDeviceClass.PROBLEM,
            icon="mdi:water-alert-outline",
        ),
    },
]


class SimplePlantMonitorProblem(BinarySensorEntity):
    """Binary sensor that triggers when a monitored metric is outside its threshold range."""

    _attr_has_entity_name = True
    _fallback_value = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        description: BinarySensorEntityDescription,
        metric: str,
    ) -> None:
        """Initialize the monitor problem binary sensor."""
        super().__init__()
        self.entity_description = description
        self.coordinator: SimplePlantCoordinator = hass.data[DOMAIN][entry.entry_id]
        self._metric = metric
        self._source_entity_id: str = entry.data[f"{metric}_sensor"]

        device = self.coordinator.device
        self.entity_id = f"binary_sensor.{DOMAIN}_{description.key}_{device}"
        self._attr_unique_id = f"{DOMAIN}_{description.key}_{device}"
        self._attr_native_value: bool | None = None
        self._attr_device_info = self.coordinator.device_info

    @property
    def is_on(self) -> bool:
        """Return true if the metric is outside its threshold range."""
        return self._fallback_value if self._attr_native_value is None else self._attr_native_value

    async def async_added_to_hass(self) -> None:
        """Run when entity added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                self._source_entity_id,
                self._update_state,
            )
        )
        await self._update_state()

    async def _update_state(
        self,
        _event: Event[EventStateChangedData] | None = None,
    ) -> None:
        """Update from coordinator."""
        result = self.coordinator.get_metric_problem(self._metric)
        self._attr_native_value = result if result is not None else self._fallback_value
        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary_sensor platform."""
    entities: list[BinarySensorEntity] = [
        entity["class"](hass, entry, entity["description"]) for entity in ENTITIES
    ]
    for metric in MONITORED_METRICS:
        if not entry.data.get(f"{metric}_sensor"):
            continue
        description = BinarySensorEntityDescription(
            key=f"{metric}_problem",
            translation_key=f"{metric}_problem",
            device_class=BinarySensorDeviceClass.PROBLEM,
        )
        entities.append(SimplePlantMonitorProblem(hass, entry, description, metric))
    async_add_entities(entities)
