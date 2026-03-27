# 🌊 Irish Tide Times — Home Assistant Custom Integration

A custom Home Assistant integration that displays Irish tide times and predictions
using the [WorldTides API](https://www.worldtides.info), which covers all Irish
coastal locations with accurate harmonic tide predictions.

---

## Features

- **Next High Tide** — time and height in metres
- **Next Low Tide** — time and height in metres
- **Tide State** — Rising or Falling
- **Time Until Next Tide** — e.g. "2h 15m"
- **Today's Full Schedule** — all high/low tides for the day as attributes
- Works for **any Irish coastal location** — just set lat/lon
- Updates every **30 minutes** by default (configurable)

---

## Installation

### Step 1 — Get a Free WorldTides API Key

1. Go to [https://www.worldtides.info/developer](https://www.worldtides.info/developer)
2. Sign up for a free account
3. Each poll uses ~2 credits. At 30-min intervals ≈ 96 polls/day = ~5,760/month
   - **Tip:** Set `scan_interval: 86400` (daily) to use ~62 credits/month.

### Step 2 — Copy the Integration Files

Copy the `custom_components/irish_tides/` folder into your Home Assistant
configuration directory:

```
config/
└── custom_components/
    └── irish_tides/
        ├── __init__.py
        ├── manifest.json
        └── sensor.py
```

If you use Home Assistant OS or Supervised, this is typically:
`/config/custom_components/irish_tides/`

You can use the **File Editor** add-on or **SSH** to upload the files.

### Step 3 — Configure in configuration.yaml

Add the following to your `configuration.yaml`:

```yaml
sensor:
  - platform: irish_tides
    api_key: "YOUR_WORLDTIDES_API_KEY_HERE"
    name: "Killala Bay Tides"
    latitude: 54.21
    longitude: -9.22
    station_distance: 50
    scan_interval: 3600
```

See `configuration_snippet.yaml` for coordinates of common Irish locations.

### Step 4 — Restart Home Assistant

Go to **Settings → System → Restart**.

### Step 5 — Add the Lovelace Dashboard Card

Go to your dashboard, click Edit → Add Card → Manual, and paste the YAML
from `lovelace/tide_cards.yaml`.

---

## Sensor Entities Created

After setup, three sensor entities will appear:

| Entity ID | Description |
|-----------|-------------|
| `sensor.killala_bay_tides_next_high_tide` | Time of next high tide |
| `sensor.killala_bay_tides_next_low_tide` | Time of next low tide |
| `sensor.killala_bay_tides_state` | Rising / Falling |

*(Entity names depend on the `name:` you set in configuration.yaml)*

---

## Sensor Attributes

### Next High / Low Tide sensors include:
- `height_m` — tide height in metres (above LAT datum)
- `time_until` — human-readable time until the tide (e.g. "2h 15m")
- `station` — nearest tide station name
- `unix_timestamp` — raw Unix timestamp
- `today_tides` — list of all today's tides:
  ```json
  [
    {"type": "Low",  "time": "04:12", "height_m": 0.43},
    {"type": "High", "time": "10:28", "height_m": 4.21},
    {"type": "Low",  "time": "16:44", "height_m": 0.38},
    {"type": "High", "time": "22:51", "height_m": 4.15}
  ]
  ```

---

## Common Irish Coastal Coordinates

| Location | Latitude | Longitude |
|----------|----------|-----------|
| Ballina / Killala Bay | 54.21 | -9.22 |
| Sligo | 54.27 | -8.47 |
| Killybegs | 54.63 | -8.44 |
| Galway | 53.27 | -9.05 |
| Westport / Clew Bay | 53.80 | -9.52 |
| Clifden | 53.49 | -10.02 |
| Dublin | 53.35 | -6.22 |
| Dun Laoghaire | 53.29 | -6.13 |
| Howth | 53.38 | -6.06 |
| Wexford | 52.33 | -6.46 |
| Waterford | 52.16 | -7.10 |
| Cork Harbour | 51.85 | -8.30 |
| Kinsale | 51.71 | -8.52 |
| Ballycotton | 51.83 | -7.99 |

Find any location's coordinates at [https://www.latlong.net](https://www.latlong.net)

---

## Example Automation — High Tide Alert

```yaml
automation:
  - alias: "High Tide Alert"
    trigger:
      - platform: template
        value_template: >
          {% set attr = state_attr('sensor.killala_bay_tides_next_high_tide', 'time_until') %}
          {{ attr == '1h 0m' or attr == '0h 59m' }}
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "🌊 High Tide Soon!"
          message: >
            High tide at {{ states('sensor.killala_bay_tides_next_high_tide') }}
            — {{ state_attr('sensor.killala_bay_tides_next_high_tide', 'height_m') }}m
```

---

## Troubleshooting

**No data / "Unavailable" state:**
- Check your API key is correct in configuration.yaml
- Check your lat/lon coordinates are on the Irish coast
- Check Home Assistant logs: **Settings → System → Logs**, search for "irish_tides"

**Wrong tide times:**
- Times are displayed in your Home Assistant local timezone
- Ireland uses IST (UTC+1) in summer, GMT (UTC+0) in winter

**API credit usage:**
- Reduce `scan_interval` to `3600` (hourly) or `7200` (every 2 hours)

---

## Data Source

Tide predictions are sourced from **[WorldTides](https://www.worldtides.info)**,
which uses harmonic analysis of measured station data and satellite observations.
Accuracy is typically within 5–15 minutes of actual tide times.

---

## License

MIT — free to use and modify.
