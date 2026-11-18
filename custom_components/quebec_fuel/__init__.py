"""Quebec Fuel Prices integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import QuebecFuelCoordinator

PLATFORMS = [Platform.SENSOR]

type QuebecFuelConfigEntry = ConfigEntry[QuebecFuelCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: QuebecFuelConfigEntry) -> bool:
    """Set up Quebec Fuel Prices from a config entry."""
    coordinator = QuebecFuelCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    _remove_stale_devices(hass, entry, coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: QuebecFuelConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: QuebecFuelConfigEntry, device: dr.DeviceEntry
) -> bool:
    """Allow manual deletion of a station device that is no longer tracked."""
    return not any(
        identifier[0] == DOMAIN and identifier[1] in entry.runtime_data.data
        for identifier in device.identifiers
    )


def _remove_stale_devices(
    hass: HomeAssistant, entry: QuebecFuelConfigEntry, coordinator: QuebecFuelCoordinator
) -> None:
    """Remove devices for stations no longer matched (e.g. after shrinking the radius)."""
    registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(registry, entry.entry_id):
        station_ids = {i[1] for i in device.identifiers if i[0] == DOMAIN}
        if station_ids and not station_ids & coordinator.data.keys():
            registry.async_update_device(
                device.id, remove_config_entry_id=entry.entry_id
            )
