"""Sensor platform for Quebec Fuel Prices."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, FUEL_TYPES
from .coordinator import QuebecFuelCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities, and dynamically add new stations."""
    coordinator: QuebecFuelCoordinator = hass.data[DOMAIN][entry.entry_id]
    known_stations: set[str] = set()

    @callback
    def _add_new_stations() -> None:
        """Check for new stations and add entities."""
        new_entities = []
        for station_id, station in coordinator.data.items():
            if station_id in known_stations:
                continue
            known_stations.add(station_id)
            for fuel_type in FUEL_TYPES:
                new_entities.append(
                    QuebecFuelPriceSensor(coordinator, station_id, fuel_type)
                )
            new_entities.append(
                QuebecFuelAddressSensor(coordinator, station_id)
            )
        if new_entities:
            async_add_entities(new_entities)

    # Add initial stations
    _add_new_stations()

    # Listen for future updates to catch new stations
    entry.async_on_unload(
        coordinator.async_add_listener(_add_new_stations)
    )


def _device_info(coordinator: QuebecFuelCoordinator, station_id: str) -> DeviceInfo:
    """Build shared DeviceInfo for a station."""
    station = coordinator.data[station_id]
    return DeviceInfo(
        identifiers={(DOMAIN, station_id)},
        name=f"{station['brand']} - {station['name']}",
        manufacturer=station["brand"],
        model="Gas Station",
        configuration_url="https://regieessencequebec.ca/",
    )


class QuebecFuelPriceSensor(CoordinatorEntity[QuebecFuelCoordinator], SensorEntity):
    """Sensor for a fuel price at a specific station."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "¢/L"
    _attr_icon = "mdi:gas-station"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: QuebecFuelCoordinator,
        station_id: str,
        fuel_type: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._station_id = station_id
        self._fuel_type = fuel_type

        self._attr_unique_id = f"{station_id}_{fuel_type}".lower()
        self._attr_name = fuel_type
        self._attr_device_info = _device_info(coordinator, station_id)

    @property
    def native_value(self) -> float | None:
        """Return the fuel price in cents/litre."""
        station = self.coordinator.data.get(self._station_id)
        if station is None:
            return None
        return station["prices"].get(self._fuel_type)

    @property
    def available(self) -> bool:
        """Return True if the station and fuel type are available."""
        if not super().available:
            return False
        station = self.coordinator.data.get(self._station_id)
        return station is not None and self._fuel_type in station.get("prices", {})

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional attributes."""
        station = self.coordinator.data.get(self._station_id)
        if station is None:
            return {}
        return {
            "address": station["address"],
            "postal_code": station["postal_code"],
            "region": station["region"],
            "brand": station["brand"],
            "latitude": station["latitude"],
            "longitude": station["longitude"],
        }


class QuebecFuelAddressSensor(CoordinatorEntity[QuebecFuelCoordinator], SensorEntity):
    """Sensor showing the station address (diagnostic/info)."""

    _attr_icon = "mdi:map-marker"
    _attr_has_entity_name = True
    _attr_name = "Address"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: QuebecFuelCoordinator,
        station_id: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._station_id = station_id

        self._attr_unique_id = f"{station_id}_address"
        self._attr_device_info = _device_info(coordinator, station_id)

    @property
    def native_value(self) -> str | None:
        """Return the station address."""
        station = self.coordinator.data.get(self._station_id)
        if station is None:
            return None
        return station["address"]

    @property
    def extra_state_attributes(self) -> dict:
        """Return location attributes."""
        station = self.coordinator.data.get(self._station_id)
        if station is None:
            return {}
        return {
            "postal_code": station["postal_code"],
            "region": station["region"],
            "latitude": station["latitude"],
            "longitude": station["longitude"],
        }
