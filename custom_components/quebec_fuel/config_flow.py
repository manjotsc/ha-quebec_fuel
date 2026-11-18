"""Config flow for Quebec Fuel Prices."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    LocationSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_CENTER_LAT,
    CONF_CENTER_LON,
    CONF_RADIUS_KM,
    CONF_STATION_IDS,
    DOMAIN,
)
from .coordinator import active_stations, async_fetch_stations

_LOGGER = logging.getLogger(__name__)

CONF_LOCATION = "location"
DEFAULT_RADIUS_KM = 10


def _radius_schema(radius_km: float, lat: float, lon: float) -> vol.Schema:
    """Schema for radius mode: km box + map picker."""
    return vol.Schema(
        {
            vol.Required(CONF_RADIUS_KM, default=radius_km): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=200,
                    step=1,
                    unit_of_measurement="km",
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_LOCATION, default={"latitude": lat, "longitude": lon}
            ): LocationSelector(),
        }
    )


def _stations_schema(stations: dict[str, str], default: list[str] | None = None) -> vol.Schema:
    """Schema for picking specific stations."""
    options = [SelectOptionDict(value=sid, label=label) for sid, label in stations.items()]
    # Optional on purpose: the HA frontend pre-fills a *required* select with its
    # first option, which would pre-select a random station. Emptiness is
    # validated in the flow instead ("no_stations").
    key = (
        vol.Optional(CONF_STATION_IDS, default=default)
        if default
        else vol.Optional(CONF_STATION_IDS)
    )
    return vol.Schema(
        {
            key: SelectSelector(
                SelectSelectorConfig(
                    options=options,
                    multiple=True,
                    custom_value=False,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
        }
    )


def _radius_entry(hass: HomeAssistant, user_input: dict[str, Any]) -> tuple[dict, str, str]:
    """Build (data, title, unique_id) for a radius entry from form input."""
    radius = float(user_input[CONF_RADIUS_KM])
    radius_label = f"{radius:g}"
    location = user_input[CONF_LOCATION]
    lat, lon = location["latitude"], location["longitude"]

    data: dict[str, Any] = {CONF_RADIUS_KM: radius}
    # Only store a custom center if it differs from home
    if abs(lat - hass.config.latitude) > 0.0001 or abs(lon - hass.config.longitude) > 0.0001:
        data[CONF_CENTER_LAT] = lat
        data[CONF_CENTER_LON] = lon
        title = f"Stations within {radius_label} km of ({lat:.4f}, {lon:.4f})"
    else:
        title = f"Stations within {radius_label} km of home"

    unique_id = (
        f"radius_{data.get(CONF_CENTER_LAT, 'home')}_"
        f"{data.get(CONF_CENTER_LON, 'home')}_{radius}"
    )
    return data, title, unique_id


def _stations_entry(selected: list[str]) -> tuple[dict, str, str]:
    """Build (data, title, unique_id) for a station-pick entry."""
    title = f"{len(selected)} station{'s' if len(selected) != 1 else ''}"
    return {CONF_STATION_IDS: selected}, title, f"stations_{'_'.join(sorted(selected))}"


class QuebecFuelConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Quebec Fuel Prices."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._stations: dict[str, str] = {}

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Choose setup mode: nearby radius or pick stations."""
        return self.async_show_menu(step_id="user", menu_options=["radius", "stations"])

    async def async_step_radius(self, user_input=None) -> ConfigFlowResult:
        """Configure radius-based tracking with optional custom center."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await async_fetch_stations(self.hass)
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Error fetching station data")
                errors["base"] = "cannot_connect"
            else:
                data, title, unique_id = _radius_entry(self.hass, user_input)
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=title, data=data)

        return self.async_show_form(
            step_id="radius",
            data_schema=self.add_suggested_values_to_schema(
                _radius_schema(
                    DEFAULT_RADIUS_KM, self.hass.config.latitude, self.hass.config.longitude
                ),
                user_input,
            ),
            errors=errors,
        )

    async def async_step_stations(self, user_input=None) -> ConfigFlowResult:
        """Pick specific stations."""
        errors: dict[str, str] = {}

        if not self._stations:
            try:
                self._stations = active_stations(await async_fetch_stations(self.hass))
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Error fetching station data")
                return self.async_abort(reason="cannot_connect")

        if user_input is not None:
            selected = user_input.get(CONF_STATION_IDS, [])
            if not selected:
                errors["base"] = "no_stations"
            else:
                data, title, unique_id = _stations_entry(selected)
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=title, data=data)

        return self.async_show_form(
            step_id="stations",
            data_schema=_stations_schema(self._stations),
            errors=errors,
            description_placeholders={"count": str(len(self._stations))},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow handler."""
        return QuebecFuelOptionsFlow()


class QuebecFuelOptionsFlow(OptionsFlow):
    """Options flow to reconfigure after setup."""

    def __init__(self) -> None:
        """Initialize."""
        self._stations: dict[str, str] = {}

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        """Route to the step matching the entry's mode."""
        if CONF_RADIUS_KM in self.config_entry.data:
            return await self.async_step_radius()
        return await self.async_step_stations()

    async def async_step_radius(self, user_input=None) -> ConfigFlowResult:
        """Change radius and center point."""
        current = self.config_entry.data
        errors: dict[str, str] = {}
        if user_input is not None:
            data, title, unique_id = _radius_entry(self.hass, user_input)
            if self._save(data, title, unique_id):
                return self.async_create_entry(title="", data={})
            errors["base"] = "already_configured"

        return self.async_show_form(
            step_id="radius",
            data_schema=_radius_schema(
                current[CONF_RADIUS_KM],
                current.get(CONF_CENTER_LAT, self.hass.config.latitude),
                current.get(CONF_CENTER_LON, self.hass.config.longitude),
            ),
            errors=errors,
        )

    async def async_step_stations(self, user_input=None) -> ConfigFlowResult:
        """Change the tracked stations."""
        errors: dict[str, str] = {}

        if not self._stations:
            try:
                self._stations = active_stations(await async_fetch_stations(self.hass))
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Error fetching station data")
                return self.async_abort(reason="cannot_connect")

        if user_input is not None:
            selected = user_input.get(CONF_STATION_IDS, [])
            if not selected:
                errors["base"] = "no_stations"
            else:
                data, title, unique_id = _stations_entry(selected)
                if self._save(data, title, unique_id):
                    return self.async_create_entry(title="", data={})
                errors["base"] = "already_configured"

        current = [
            sid for sid in self.config_entry.data.get(CONF_STATION_IDS, [])
            if sid in self._stations
        ]
        return self.async_show_form(
            step_id="stations",
            data_schema=_stations_schema(self._stations, current),
            errors=errors,
            description_placeholders={"count": str(len(self._stations))},
        )

    def _save(self, data: dict, title: str, unique_id: str) -> bool:
        """Update the entry and schedule a reload. False if it would duplicate another entry."""
        entries = self.hass.config_entries
        if any(
            e.unique_id == unique_id and e.entry_id != self.config_entry.entry_id
            for e in entries.async_entries(DOMAIN)
        ):
            return False
        entries.async_update_entry(
            self.config_entry, data=data, title=title, unique_id=unique_id
        )
        entries.async_schedule_reload(self.config_entry.entry_id)
        return True
