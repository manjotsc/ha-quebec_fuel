"""Config flow for Quebec Fuel Prices."""
from __future__ import annotations

import gzip

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import json
from homeassistant.helpers.selector import selector

from .const import CONF_CENTER_LAT, CONF_CENTER_LON, CONF_RADIUS_KM, CONF_STATION_IDS, DATA_URL, DOMAIN
from .coordinator import _station_id


async def _fetch_stations(hass) -> dict:
    """Fetch and decompress station data, return parsed JSON."""
    session = async_get_clientsession(hass)
    timeout = aiohttp.ClientTimeout(total=30)
    resp = await session.get(DATA_URL, timeout=timeout)
    resp.raise_for_status()
    raw_bytes = await resp.read()
    try:
        decompressed = gzip.decompress(raw_bytes)
        return json.loads(decompressed)
    except gzip.BadGzipFile:
        return json.loads(raw_bytes)


class QuebecFuelConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Quebec Fuel Prices."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._stations: dict = {}

    async def async_step_user(self, user_input=None):
        """Choose setup mode: nearby radius or pick stations."""
        if user_input is not None:
            if user_input["mode"] == "radius":
                return await self.async_step_radius()
            return await self.async_step_stations()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("mode", default="radius"): vol.In(
                        {"radius": "Stations within radius of home", "pick": "Pick specific stations"}
                    ),
                }
            ),
        )

    async def async_step_radius(self, user_input=None):
        """Configure radius-based tracking with optional custom center."""
        errors = {}
        if user_input is not None:
            try:
                await _fetch_stations(self.hass)
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                entry_data = {CONF_RADIUS_KM: user_input[CONF_RADIUS_KM]}

                lat = user_input.get(CONF_CENTER_LAT)
                lon = user_input.get(CONF_CENTER_LON)
                home_lat = self.hass.config.latitude
                home_lon = self.hass.config.longitude

                # Only store custom center if it differs from home
                is_custom = (
                    lat is not None
                    and lon is not None
                    and (abs(lat - home_lat) > 0.0001 or abs(lon - home_lon) > 0.0001)
                )

                if is_custom:
                    entry_data[CONF_CENTER_LAT] = lat
                    entry_data[CONF_CENTER_LON] = lon
                    title = f"Stations within {user_input[CONF_RADIUS_KM]} km of ({lat:.4f}, {lon:.4f})"
                else:
                    title = f"Stations within {user_input[CONF_RADIUS_KM]} km of home"

                # Prevent duplicate radius entries with same params
                await self.async_set_unique_id(
                    f"radius_{entry_data.get(CONF_CENTER_LAT, 'home')}_{entry_data.get(CONF_CENTER_LON, 'home')}_{entry_data[CONF_RADIUS_KM]}"
                )
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title=title, data=entry_data)

        home_lat = self.hass.config.latitude
        home_lon = self.hass.config.longitude

        return self.async_show_form(
            step_id="radius",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_RADIUS_KM, default=10): vol.Coerce(float),
                    vol.Optional(CONF_CENTER_LAT, default=home_lat): vol.Coerce(float),
                    vol.Optional(CONF_CENTER_LON, default=home_lon): vol.Coerce(float),
                }
            ),
            errors=errors,
        )

    async def async_step_stations(self, user_input=None):
        """Pick specific stations."""
        errors = {}

        if not self._stations:
            try:
                data = await _fetch_stations(self.hass)
            except Exception:
                return self.async_abort(reason="cannot_connect")

            for feature in data.get("features", []):
                props = feature["properties"]
                if props.get("Status") != "En opération":
                    continue
                sid = _station_id(feature)
                label = f"{props.get('brand', '')} - {props.get('Name', '')} ({props.get('Address', '')})"
                self._stations[sid] = label

        if user_input is not None:
            selected = user_input[CONF_STATION_IDS]
            if not selected:
                errors["base"] = "no_stations"
            else:
                # Prevent duplicate station-pick entries
                unique = "_".join(sorted(selected))
                await self.async_set_unique_id(f"stations_{unique}")
                self._abort_if_unique_id_configured()

                names = [self._stations[s] for s in selected if s in self._stations]
                title = f"{len(names)} station(s)"
                return self.async_create_entry(
                    title=title,
                    data={CONF_STATION_IDS: selected},
                )

        sorted_stations = dict(sorted(self._stations.items(), key=lambda x: x[1]))

        options = [
            {"value": sid, "label": label}
            for sid, label in sorted_stations.items()
        ]

        return self.async_show_form(
            step_id="stations",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STATION_IDS): selector({
                        "select": {
                            "options": options,
                            "multiple": True,
                            "custom_value": False,
                            "mode": "dropdown",
                        }
                    }),
                }
            ),
            errors=errors,
            description_placeholders={"count": str(len(sorted_stations))},
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        """Return the options flow handler."""
        return QuebecFuelOptionsFlow(config_entry)


class QuebecFuelOptionsFlow(config_entries.OptionsFlow):
    """Options flow to reconfigure after setup."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle options."""
        if user_input is not None:
            # Merge new options into entry data
            new_data = {**self._config_entry.data, **user_input}
            self.hass.config_entries.async_update_entry(
                self._config_entry, data=new_data
            )
            await self.hass.config_entries.async_reload(self._config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        current = self._config_entry.data
        schema_fields = {}

        if CONF_RADIUS_KM in current:
            home_lat = self.hass.config.latitude
            home_lon = self.hass.config.longitude
            schema_fields[vol.Required(CONF_RADIUS_KM, default=current[CONF_RADIUS_KM])] = vol.Coerce(float)
            schema_fields[vol.Optional(CONF_CENTER_LAT, default=current.get(CONF_CENTER_LAT, home_lat))] = vol.Coerce(float)
            schema_fields[vol.Optional(CONF_CENTER_LON, default=current.get(CONF_CENTER_LON, home_lon))] = vol.Coerce(float)

        if not schema_fields:
            # Station-pick mode — no reconfigurable options yet
            return self.async_abort(reason="no_options")

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_fields),
        )
