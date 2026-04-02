"""Data update coordinator for Quebec Fuel Prices."""
from __future__ import annotations

import gzip
import logging
from datetime import timedelta
from math import asin, cos, radians, sin, sqrt

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import json
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    CONF_CENTER_LAT,
    CONF_CENTER_LON,
    CONF_RADIUS_KM,
    CONF_STATION_IDS,
    DATA_URL,
    DEFAULT_SCAN_INTERVAL_MINUTES,
)

_LOGGER = logging.getLogger(__name__)


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in km between two points."""
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 6371 * 2 * asin(sqrt(a))


def _station_id(feature: dict) -> str:
    """Generate a stable ID from coordinates only (name-independent)."""
    coords = feature["geometry"]["coordinates"]
    # 5 decimal places = ~1m precision, stable even if name changes
    return f"{coords[1]:.5f}_{coords[0]:.5f}"


class QuebecFuelCoordinator(DataUpdateCoordinator):
    """Coordinator to fetch Quebec fuel station data."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name="Quebec Fuel Prices",
            config_entry=config_entry,
            update_interval=timedelta(minutes=DEFAULT_SCAN_INTERVAL_MINUTES),
            always_update=False,
        )
        self._session = async_get_clientsession(hass)

    async def _async_update_data(self) -> dict:
        """Fetch data from regieessencequebec.ca."""
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            resp = await self._session.get(DATA_URL, timeout=timeout)
            resp.raise_for_status()
            raw_bytes = await resp.read()

            # Handle gzip: the URL serves a .gz file
            try:
                decompressed = gzip.decompress(raw_bytes)
                data = json.loads(decompressed)
            except gzip.BadGzipFile:
                # Fallback: server already decompressed via Content-Encoding
                data = json.loads(raw_bytes)

        except Exception as err:
            raise UpdateFailed(f"Error fetching fuel data: {err}") from err

        features = data.get("features", [])
        station_ids = self.config_entry.data.get(CONF_STATION_IDS, [])
        radius_km = self.config_entry.data.get(CONF_RADIUS_KM)
        center_lat = self.config_entry.data.get(
            CONF_CENTER_LAT, self.hass.config.latitude
        )
        center_lon = self.config_entry.data.get(
            CONF_CENTER_LON, self.hass.config.longitude
        )

        stations = {}
        for feature in features:
            props = feature["properties"]
            coords = feature["geometry"]["coordinates"]

            if props.get("Status") != "En opération":
                continue

            sid = _station_id(feature)

            # Filter: specific stations
            if station_ids and sid not in station_ids:
                continue

            # Filter: radius
            if radius_km and not station_ids:
                dist = _haversine(center_lat, center_lon, coords[1], coords[0])
                if dist > radius_km:
                    continue

            prices = {}
            for p in props.get("Prices", []):
                if p.get("IsAvailable"):
                    raw = str(p.get("Price", "0")).rstrip("c¢").strip()
                    try:
                        prices[p["GasType"]] = float(raw)
                    except (ValueError, TypeError):
                        pass

            stations[sid] = {
                "name": props.get("Name", "Unknown"),
                "brand": props.get("brand", "Unknown"),
                "address": props.get("Address", ""),
                "postal_code": props.get("PostalCode", ""),
                "region": props.get("Region", ""),
                "latitude": coords[1],
                "longitude": coords[0],
                "prices": prices,
            }

        return stations
