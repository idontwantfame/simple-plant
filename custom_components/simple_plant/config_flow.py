"""Adds config flow for Simple PLant."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import aiofiles
import voluptuous as vol
from homeassistant.components.file_upload import process_uploaded_file
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.util import slugify
from homeassistant.util.dt import as_local, utcnow

from .const import DOMAIN, HEALTH_OPTIONS, IMAGES_MIME_TYPES, LOGGER, MONITORED_METRICS, STORAGE_DIR

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

## UTILS


async def save_image(hass: HomeAssistant, file_id: str) -> str:
    """Permanently save an uploaded image."""
    with process_uploaded_file(hass, file_id) as uploaded_file:
        # Save the file
        storage_dir = Path(hass.config.path(STORAGE_DIR))
        storage_dir.mkdir(parents=True, exist_ok=True)

        suffix = uploaded_file.suffix
        if suffix not in IMAGES_MIME_TYPES:
            raise ValueError
        file_path = storage_dir / f"{file_id}{suffix}"

        # Safely copy the file using async operations
        async with aiofiles.open(file_path, "wb") as destination_file:  # noqa: SIM117
            async with aiofiles.open(uploaded_file, "rb") as source_file:
                await destination_file.write(await source_file.read())

        # relative path
        return f"/{STORAGE_DIR}/{file_path.name}"


def remove_photo(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove the photo file of a config entry."""
    file_path: Path | None = None
    try:
        # Get the photo path from the entry's data
        photo_path = entry.data.get("photo")
        if photo_path:
            # Convert url path to actual file path
            file_path = Path(str(hass.config.path(photo_path.lstrip("/"))))

            LOGGER.info("Trying to remove: %s", photo_path)

            # Check if file exists before trying to remove it
            if file_path.exists():
                file_path.unlink()
                LOGGER.info("Successfully removed image file: %s", file_path)
            else:
                LOGGER.warning("Image file not found: %s", file_path)
    except OSError as err:
        LOGGER.error("Error reading image file %s: %s", file_path, err)


## UTILS - SENSOR/THRESHOLD FORMS


def sensors_form(suggested_values: dict | None = None) -> vol.Schema:
    """Return a form for linking environmental sensors to the plant."""
    schema_dict: dict = {}
    for metric, config in MONITORED_METRICS.items():
        suggested = (suggested_values or {}).get(f"{metric}_sensor") or ""
        schema_dict[
            vol.Optional(
                f"{metric}_sensor",
                description={"suggested_value": suggested},
            )
        ] = selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain="sensor",
                device_class=config["device_class"],
                multiple=False,
            )
        )
    return vol.Schema(schema_dict)


def thresholds_form(
    sensors_data: dict,
    suggested_thresholds: dict | None = None,
) -> vol.Schema:
    """Return a form for configuring metric thresholds (only for linked sensors)."""
    schema_dict: dict = {}
    for metric, config in MONITORED_METRICS.items():
        if not sensors_data.get(f"{metric}_sensor"):
            continue
        suggested = suggested_thresholds or {}
        schema_dict[
            vol.Optional(
                f"{metric}_min",
                default=suggested.get(f"{metric}_min", config["default_min"]),
            )
        ] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=config["range_min"],
                max=config["range_max"],
                step=config["step"],
                mode=selector.NumberSelectorMode.BOX,
                unit_of_measurement=config["unit"],
            )
        )
        if config["has_max"]:
            schema_dict[
                vol.Optional(
                    f"{metric}_max",
                    default=suggested.get(f"{metric}_max", config["default_max"]),
                )
            ] = selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=config["range_min"],
                    max=config["range_max"],
                    step=config["step"],
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement=config["unit"],
                )
            )
    return vol.Schema(schema_dict)


## CONFIG FLOW SCHEMAS


def user_form() -> vol.Schema:
    """Return a new device form."""
    LOGGER.debug("config_flow, 1st call : displaying form")
    return vol.Schema(
        {
            vol.Required("name"): selector.TextSelector(
                selector.TextSelectorConfig(multiline=False, multiple=False)
            ),
            vol.Required("last_watered"): selector.DateSelector(
                selector.DateSelectorConfig(),
            ),
            vol.Required("days_between_waterings"): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=60,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="days",
                ),
            ),
            vol.Required("health"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    {
                        "options": HEALTH_OPTIONS,
                        "custom_value": False,
                        "sort": False,
                    }
                )
            ),
            vol.Optional("species", default=""): str,
            vol.Optional("photo"): selector.FileSelector(
                selector.FileSelectorConfig(accept="image/*")
            ),
        }
    )


def option_form(suggested_species: str | None = None) -> vol.Schema:
    """Return a device reconfiguration form."""
    LOGGER.debug("option_flow, 1st call : displaying form")
    return vol.Schema(
        {
            vol.Optional(
                "species",
                default="",
                description={"suggested_value": suggested_species or ""},
            ): str,
            vol.Optional("photo"): selector.FileSelector(
                selector.FileSelectorConfig(accept="image/*")
            ),
        }
    )


## CONFIG FLOWS


class SimplePlantFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for Simple Plant."""

    VERSION = 1

    def __init__(self) -> None:
        """Init."""
        self._user_inputs: dict = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:  # noqa: ARG004
        """Get options flow for this handler."""
        return SimplePlantOptionFlowHandler()

    async def async_step_user(self, user_input: dict | None = None) -> ConfigFlowResult:
        """
        Provide Base Plant information Config Flow.

        1st call = return form to show
        2nd call = return form with user input
        """
        if user_input is None:
            # 1st call
            return self.async_show_form(step_id="user", data_schema=user_form())
        # 2nd call
        # Verify name
        domain_entries = self.hass.config_entries.async_entries(domain=DOMAIN)
        domain_entries_title_slugs = [slugify(entry.title) for entry in domain_entries]
        LOGGER.debug(domain_entries_title_slugs)
        if slugify(user_input["name"]) in domain_entries_title_slugs:
            return self.async_show_form(
                step_id="user",
                data_schema=user_form(),
                errors={"base": "name_exist"},
            )
        user_input["name_by_user"] = user_input["name"]
        # Verify date
        if "last_watered" in user_input:
            input_date = datetime.fromisoformat(user_input["last_watered"]).date()
            if input_date > as_local(utcnow()).date():
                return self.async_show_form(
                    step_id="user",
                    data_schema=user_form(),
                    errors={"base": "invalid_future_date"},
                )
        if user_input.get("photo"):
            try:
                user_input["photo"] = await save_image(self.hass, user_input["photo"])
            except ValueError:
                return self.async_show_form(
                    step_id="user",
                    data_schema=user_form(),
                    errors={"base": "upload_failed_type"},
                )

        self._user_inputs.update(user_input)
        return await self.async_step_advanced_sensors()


    async def async_step_advanced_sensors(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Select optional environmental sensors to link to this plant."""
        if user_input is None:
            return self.async_show_form(
                step_id="advanced_sensors",
                data_schema=sensors_form(),
            )
        for metric in MONITORED_METRICS:
            key = f"{metric}_sensor"
            if user_input.get(key):
                self._user_inputs[key] = user_input[key]
        if any(self._user_inputs.get(f"{metric}_sensor") for metric in MONITORED_METRICS):
            return await self.async_step_advanced_thresholds()
        return self.async_create_entry(title=self._user_inputs["name"], data=self._user_inputs)

    async def async_step_advanced_thresholds(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Set warning thresholds for linked sensors."""
        if user_input is None:
            return self.async_show_form(
                step_id="advanced_thresholds",
                data_schema=thresholds_form(self._user_inputs),
            )
        self._user_inputs.update(user_input)
        return self.async_create_entry(title=self._user_inputs["name"], data=self._user_inputs)


class SimplePlantOptionFlowHandler(OptionsFlow):
    """Reconfiguration flow for Simple Plant."""

    def __init__(self) -> None:
        """Init."""
        self.user_inputs: dict = {}

    async def async_step_init(self, user_input: dict | None = None) -> ConfigFlowResult:
        """
        Provide new information.

        1st call = return form to show
        2nd call = return form with user input
        """
        form = option_form(self.config_entry.data.get("species"))

        if user_input is None:
            # 1st call
            return self.async_show_form(step_id="init", data_schema=form)
        # 2nd call
        if user_input.get("species"):
            self.user_inputs["species"] = user_input["species"]

        if user_input.get("photo"):
            try:
                file_id = user_input["photo"]
                self.user_inputs["photo"] = await save_image(self.hass, file_id)
                remove_photo(self.hass, self.config_entry)
            except ValueError:
                return self.async_show_form(
                    step_id="init",
                    data_schema=form,
                    errors={"base": "upload_failed_type"},
                )

        return await self.async_step_advanced_sensors()

    async def async_step_advanced_sensors(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Select optional environmental sensors to link to this plant."""
        if user_input is None:
            current = {
                f"{m}_sensor": self.config_entry.data.get(f"{m}_sensor", "")
                for m in MONITORED_METRICS
            }
            return self.async_show_form(
                step_id="advanced_sensors",
                data_schema=sensors_form(current),
            )
        for metric in MONITORED_METRICS:
            key = f"{metric}_sensor"
            val = user_input.get(key)
            self.user_inputs[key] = val if val else None
        if any(self.user_inputs.get(f"{metric}_sensor") for metric in MONITORED_METRICS):
            return await self.async_step_advanced_thresholds()
        return await self.async_end()

    async def async_step_advanced_thresholds(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Set warning thresholds for linked sensors."""
        sensors_data = {**dict(self.config_entry.data), **self.user_inputs}
        if user_input is None:
            suggested: dict = {}
            for m, cfg in MONITORED_METRICS.items():
                suggested[f"{m}_min"] = self.config_entry.data.get(f"{m}_min", cfg["default_min"])
                if cfg["has_max"]:
                    suggested[f"{m}_max"] = self.config_entry.data.get(f"{m}_max", cfg["default_max"])
            return self.async_show_form(
                step_id="advanced_thresholds",
                data_schema=thresholds_form(sensors_data, suggested),
            )
        self.user_inputs.update(user_input)
        return await self.async_end()

    async def async_end(self) -> ConfigFlowResult:
        """Finish ConfigEntry modification."""
        LOGGER.info(
            "Entry %s is being recreated",
            self.config_entry.entry_id,
        )

        data = dict(self.config_entry.data)
        data.update(self.user_inputs)
        # Remove sensor keys explicitly set to None (user cleared them)
        data = {k: v for k, v in data.items() if v is not None}
        self.hass.config_entries.async_update_entry(self.config_entry, data=data)

        return self.async_create_entry(
            # No data as config entry has been modified
            title=None,
            data={},
        )
