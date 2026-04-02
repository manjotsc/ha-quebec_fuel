# Quebec Fuel Prices - Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Track real-time fuel prices from Quebec gas stations using data from the [Régie de l'énergie du Québec](https://regieessencequebec.ca/).

## Features

- **Three fuel types tracked per station**: Régulier, Super, Diesel (in ¢/L)
- **Address sensor** for each station (diagnostic entity with postal code, region, coordinates)
- **Two setup modes**:
  - **Radius** — automatically track all stations within X km of your home (or a custom location)
  - **Pick** — select specific stations from the full Quebec list
- **Dynamic discovery** — new stations appearing within your radius are automatically added
- **Options flow** — reconfigure radius and center point without removing the integration
- **Duplicate prevention** — won't allow duplicate config entries

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the three dots menu → **Custom repositories**
3. Add this repository URL and select **Integration** as the category
4. Search for "Quebec Fuel Prices" and install
5. Restart Home Assistant

### Manual

1. Copy the `custom_components/quebec_fuel/` folder into your Home Assistant `custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Quebec Fuel Prices**
3. Choose your setup mode:
   - **Radius**: Enter a radius in km. Coordinates default to your HA home location — change them to center on a different point (e.g., your workplace)
   - **Pick stations**: Select specific stations from a searchable dropdown

## Entities

Each station creates a **device** with the following sensors:

| Entity | Type | Unit | Description |
|--------|------|------|-------------|
| Régulier | Sensor | ¢/L | Regular gasoline price |
| Super | Sensor | ¢/L | Super/premium gasoline price |
| Diesel | Sensor | ¢/L | Diesel price |
| Address | Diagnostic | — | Station address with location attributes |

### Attributes on price sensors

- `address` — street address
- `postal_code` — postal code
- `region` — Quebec administrative region
- `brand` — station brand
- `latitude` / `longitude` — GPS coordinates

### Attributes on address sensor

- `postal_code`, `region`, `latitude`, `longitude`

## Data Source

Data is fetched from `regieessencequebec.ca/stations.geojson.gz` every **30 minutes**. This is the official open data feed from the Régie de l'énergie du Québec, covering ~2,300+ stations across the province.

## Example Automations

### Notify when regular fuel drops below a threshold

```yaml
automation:
  - alias: "Cheap gas alert"
    trigger:
      - platform: numeric_state
        entity_id: sensor.petro_canada_mon_station_regulier
        below: 150
    action:
      - service: notify.mobile_app
        data:
          title: "Cheap gas!"
          message: >
            Régulier at {{ state_attr('sensor.petro_canada_mon_station_regulier', 'address') }}
            is {{ states('sensor.petro_canada_mon_station_regulier') }}¢/L
```

### Template sensor for cheapest nearby regular

```yaml
template:
  - sensor:
      - name: "Cheapest Regular Nearby"
        unit_of_measurement: "¢/L"
        icon: mdi:gas-station
        state: >
          {{ states.sensor
            | selectattr('entity_id', 'match', '.*regulier$')
            | selectattr('state', 'is_number')
            | map(attribute='state')
            | map('float')
            | min }}
```

## License

MIT
