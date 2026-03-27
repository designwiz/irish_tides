"""Irish Tide Times Sensor Platform.

Retrieves tide predictions from the WorldTides API for Irish coastal locations.
Provides sensors for:
  - Next high tide (time + height)
  - Next low tide (time + height)
  - Current tide state (Rising / Falling)
  - Time until next tide
  - Full list of today's tides as attributes

API: https://www.worldtides.info/apidocs
Free key: https://www.worldtides.info/developer  (500 free credits/month)

--- IRISH STATION LOCATIONS (lat/lon) ---
Ballina / Killala Bay:   54.21, -9.22
Sligo:                   54.27, -8.47
Galway:                  53.27, -9.05
Clifden:                 53.49, -10.02
Westport:                53.80, -9.52
Killybegs:               54.63, -8.44
Dublin:                  53.35, -6.22
Dun Laoghaire:           53.29, -6.13
Wexford:                 52.33, -6.46
Waterford:               52.16, -7.10
Cork Harbour:            51.85, -8.30
Kinsale:                 51.71, -8.52
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=30)
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=30)

CONF_STATION_DISTANCE = "station_distance"

DEFAULT_NAME = "Irish Tides"
DEFAULT_STATION_DISTANCE = 50

WORLDTIDES_API_URL = "https://www.worldtides.info/api/v3"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_LATITUDE): cv.latitude,
        vol.Optional(CONF_LONGITUDE): cv.longitude,
        vol.Optional(CONF_STATION_DISTANCE, default=DEFAULT_STATION_DISTANCE): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=500)
        ),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Irish Tides sensor platform."""
    api_key = config[CONF_API_KEY]
    name = config[CONF_NAME]
    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
    station_distance = config[CONF_STATION_DISTANCE]

    tide_data = IrishTideData(api_key, latitude, longitude, station_distance)
    # Call _do_fetch directly on setup to bypass throttle on first run
    tide_data._do_fetch()

    if tide_data.data is None:
        _LOGGER.error(
            "Irish Tides: Could not retrieve tide data on startup. "
            "API key and coordinates appear valid — will retry on next poll."
        )
        # Don't return — still add entities so they retry on next update cycle

    add_entities(
        [
            IrishTideNextHighSensor(name, tide_data),
            IrishTideNextLowSensor(name, tide_data),
            IrishTideStateSensor(name, tide_data),
        ],
        True,
    )


class IrishTideData:
    """Fetches and caches tide data from the WorldTides API."""

    def __init__(self, api_key, latitude, longitude, station_distance):
        self._api_key = api_key
        self._latitude = latitude
        self._longitude = longitude
        self._station_distance = station_distance
        self.data = None
        self.extremes = []
        self.station_name = "Unknown"

    def _do_fetch(self):
        """Perform the actual API fetch. Call directly to bypass throttle."""
        try:
            params = {
                "extremes": "",
                "days": 3,
                "lat": self._latitude,
                "lon": self._longitude,
                "stationDistance": self._station_distance,
                "key": self._api_key,
                "datum": "LAT",
            }

            _LOGGER.debug("Irish Tides: Fetching from %s with params %s", WORLDTIDES_API_URL, {k: v for k, v in params.items() if k != "key"})

            response = requests.get(WORLDTIDES_API_URL, params=params, timeout=10)
            response.raise_for_status()
            result = response.json()

            _LOGGER.debug("Irish Tides: API response status=%s", result.get("status"))

            if result.get("status") != 200:
                _LOGGER.error(
                    "Irish Tides API error %s: %s",
                    result.get("status"),
                    result.get("error", "Unknown error"),
                )
                return

            self.data = result
            self.extremes = result.get("extremes", [])

            stations = result.get("stations", [])
            if stations:
                self.station_name = stations[0].get("name", "Ireland")
            else:
                self.station_name = f"{self._latitude:.2f}°N, {abs(self._longitude):.2f}°W"

            _LOGGER.info(
                "Irish Tides: Retrieved %d tide extremes for station: %s",
                len(self.extremes),
                self.station_name,
            )

        except requests.exceptions.RequestException as err:
            _LOGGER.error("Irish Tides: Network error: %s", err)
        except Exception as err:
            _LOGGER.error("Irish Tides: Unexpected error: %s", err)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Throttled update called by HA sensor refresh cycle."""
        self._do_fetch()

    def get_next_tides(self):
        """Return upcoming high and low tides relative to now (UTC)."""
        now = datetime.now(timezone.utc)
        upcoming = [e for e in self.extremes if datetime.fromtimestamp(e["dt"], tz=timezone.utc) > now]
        next_high = next((e for e in upcoming if e["type"] == "High"), None)
        next_low = next((e for e in upcoming if e["type"] == "Low"), None)
        return next_high, next_low

    def get_current_state(self):
        """Determine whether the tide is currently Rising or Falling."""
        now_ts = datetime.now(timezone.utc).timestamp()
        past = [e for e in self.extremes if e["dt"] <= now_ts]
        future = [e for e in self.extremes if e["dt"] > now_ts]

        if not past or not future:
            return "Unknown"

        last = past[-1]
        nxt = future[0]

        if last["type"] == "Low" and nxt["type"] == "High":
            return "Rising"
        elif last["type"] == "High" and nxt["type"] == "Low":
            return "Falling"
        return "Unknown"

    def format_local_time(self, unix_ts):
        """Convert a Unix timestamp to a local time string."""
        dt_utc = datetime.fromtimestamp(unix_ts, tz=timezone.utc)
        return dt_utc.astimezone().strftime("%H:%M")

    def time_until(self, unix_ts):
        """Return a human-readable 'Xhr Ymin' string until a tide."""
        now = datetime.now(timezone.utc)
        target = datetime.fromtimestamp(unix_ts, tz=timezone.utc)
        delta = target - now
        if delta.total_seconds() < 0:
            return "Passed"
        total_minutes = int(delta.total_seconds() // 60)
        hours, minutes = divmod(total_minutes, 60)
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"

    def get_todays_tides(self):
        """Return a list of today's tides as dicts."""
        now = datetime.now(timezone.utc)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        todays = [
            e for e in self.extremes
            if day_start.timestamp() <= e["dt"] < day_end.timestamp()
        ]
        return [
            {
                "type": e["type"],
                "time": self.format_local_time(e["dt"]),
                "height_m": round(e["height"], 2),
            }
            for e in todays
        ]


class IrishTideNextHighSensor(SensorEntity):
    """Sensor: Time of next high tide."""

    def __init__(self, name, tide_data):
        self._name = f"{name} Next High Tide"
        self._tide_data = tide_data
        self._state = None
        self._attrs = {}

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def icon(self):
        return "mdi:waves-arrow-up"

    @property
    def extra_state_attributes(self):
        return self._attrs

    def update(self):
        self._tide_data.update()
        next_high, _ = self._tide_data.get_next_tides()
        if next_high:
            self._state = self._tide_data.format_local_time(next_high["dt"])
            self._attrs = {
                "height_m": round(next_high["height"], 2),
                "time_until": self._tide_data.time_until(next_high["dt"]),
                "station": self._tide_data.station_name,
                "unix_timestamp": next_high["dt"],
                "today_tides": self._tide_data.get_todays_tides(),
            }
        else:
            self._state = "Unavailable"


class IrishTideNextLowSensor(SensorEntity):
    """Sensor: Time of next low tide."""

    def __init__(self, name, tide_data):
        self._name = f"{name} Next Low Tide"
        self._tide_data = tide_data
        self._state = None
        self._attrs = {}

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def icon(self):
        return "mdi:waves-arrow-down"

    @property
    def extra_state_attributes(self):
        return self._attrs

    def update(self):
        self._tide_data.update()
        _, next_low = self._tide_data.get_next_tides()
        if next_low:
            self._state = self._tide_data.format_local_time(next_low["dt"])
            self._attrs = {
                "height_m": round(next_low["height"], 2),
                "time_until": self._tide_data.time_until(next_low["dt"]),
                "station": self._tide_data.station_name,
                "unix_timestamp": next_low["dt"],
            }
        else:
            self._state = "Unavailable"


class IrishTideStateSensor(SensorEntity):
    """Sensor: Current tide state (Rising / Falling)."""

    def __init__(self, name, tide_data):
        self._name = f"{name} State"
        self._tide_data = tide_data
        self._state = None
        self._attrs = {}

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def icon(self):
        if self._state == "Rising":
            return "mdi:trending-up"
        elif self._state == "Falling":
            return "mdi:trending-down"
        return "mdi:waves"

    @property
    def extra_state_attributes(self):
        return self._attrs

    def update(self):
        self._tide_data.update()
        self._state = self._tide_data.get_current_state()
        next_high, next_low = self._tide_data.get_next_tides()
        self._attrs = {
            "station": self._tide_data.station_name,
            "next_high_time": self._tide_data.format_local_time(next_high["dt"]) if next_high else None,
            "next_high_height_m": round(next_high["height"], 2) if next_high else None,
            "next_low_time": self._tide_data.format_local_time(next_low["dt"]) if next_low else None,
            "next_low_height_m": round(next_low["height"], 2) if next_low else None,
            "today_tides": self._tide_data.get_todays_tides(),
        }
