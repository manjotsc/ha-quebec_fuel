<p align="center">
  <img src="brand/icon.svg" alt="Quebec Fuel Prices" width="120" />
</p>

<h1 align="center">Quebec Fuel Prices</h1>

<p align="center">
  <strong>Real-time fuel price tracking for Quebec gas stations in Home Assistant</strong>
</p>

<p align="center">
  <a href="https://github.com/hacs/integration"><img src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge" alt="HACS" /></a>
  <img src="https://img.shields.io/badge/Home%20Assistant-2024.1+-blue?style=for-the-badge&logo=homeassistant" alt="HA Version" />
  <img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" alt="License" />
</p>

<p align="center">
  Powered by open data from the <a href="https://regieessencequebec.ca/">Régie de l'énergie du Québec</a> — covering <strong>2,300+ stations</strong> province-wide.
</p>

---

## Features

- **3 fuel sensors per station** — Régulier, Super, Diesel (¢/L)
- **Address sensor** — diagnostic entity with postal code, region & GPS coordinates
- **Two setup modes** — radius from home/custom point, or hand-pick specific stations
- **Dynamic discovery** — new stations within your radius are added automatically
- **Reconfigurable** — change radius & center point via options flow, no need to re-add
- **Duplicate prevention** — won't create overlapping entries

---

## Installation

### HACS (Recommended)

1. Open **HACS** → three-dot menu → **Custom repositories**
2. Paste `https://github.com/manjotsc/ha-quebec_fuel`, select **Integration**
3. Search **"Quebec Fuel Prices"** → Install
4. Restart Home Assistant

### Manual

```bash
# From your HA config directory
cp -r custom_components/quebec_fuel /config/custom_components/
```

Restart Home Assistant.

---

## Setup

> **Settings → Devices & Services → Add Integration → Quebec Fuel Prices**

| Mode | Description |
|------|-------------|
| **Radius** | All stations within X km of your home — or set a custom lat/lon (workplace, cottage, etc.) |
| **Pick stations** | Searchable dropdown of every active station in Quebec |

---

## Entities

Each station appears as a **device** with 4 sensors:

| Sensor | Unit | Description |
|--------|------|-------------|
| Régulier | ¢/L | Regular gasoline price |
| Super | ¢/L | Premium gasoline price |
| Diesel | ¢/L | Diesel price |
| Address | — | Station address *(diagnostic)* |

<details>
<summary><strong>Sensor attributes</strong></summary>

**Price sensors** expose:
| Attribute | Example |
|-----------|---------|
| `address` | `1506 route 101, Saint-Édouard-de-Fabre` |
| `postal_code` | `J0Z 1Z0` |
| `region` | `Abitibi-Témiscamingue` |
| `brand` | `Crevier` |
| `latitude` | `47.21202` |
| `longitude` | `-79.36893` |

**Address sensor** exposes: `postal_code`, `region`, `latitude`, `longitude`

</details>

---

## Data Source

| | |
|---|---|
| **Endpoint** | `regieessencequebec.ca/stations.geojson.gz` |
| **Update interval** | Every 30 minutes |
| **Coverage** | ~2,300+ stations across Quebec |
| **Provider** | Régie de l'énergie du Québec (official open data) |

---

## Examples

<details>
<summary><strong>Automation: Cheap gas alert</strong></summary>

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

</details>

<details>
<summary><strong>Template: Cheapest regular nearby</strong></summary>

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

</details>

---

## License

MIT
