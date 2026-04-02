"""Constants for the Quebec Fuel Prices integration."""

DOMAIN = "quebec_fuel"

CONF_STATION_IDS = "station_ids"
CONF_RADIUS_KM = "radius_km"
CONF_CENTER_LAT = "center_lat"
CONF_CENTER_LON = "center_lon"
CONF_FUEL_TYPES = "fuel_types"

DATA_URL = "https://regieessencequebec.ca/stations.geojson.gz"

DEFAULT_SCAN_INTERVAL_MINUTES = 30

FUEL_TYPE_REGULIER = "Régulier"
FUEL_TYPE_SUPER = "Super"
FUEL_TYPE_DIESEL = "Diesel"
FUEL_TYPES = [FUEL_TYPE_REGULIER, FUEL_TYPE_SUPER, FUEL_TYPE_DIESEL]
