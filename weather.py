"""
title: OpenWebUI Weather Info by Zipcode
author: Rick Gouin
author_url: https://rickgouin.com
version: 1.0
license: GPL v3
description: Fetch current weather and forecasts using zippopotam and open-meteo.
usage: USE Weather [zipcode]
"""

from typing import Dict, Any, Tuple
from urllib.request import urlopen, Request
from urllib.parse import urlencode
import json
import datetime

# --- External endpoints (no keys required) ---
ZIP_BASE = "https://api.zippopotam.us/us/"
OPENMETEO = "https://api.open-meteo.com/v1/forecast"

# WMO -> human description
WMO_MAP: Dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Freezing drizzle (light)",
    57: "Freezing drizzle (dense)",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Freezing rain (light)",
    67: "Freezing rain (heavy)",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Rain showers (slight)",
    81: "Rain showers (moderate)",
    82: "Rain showers (violent)",
    85: "Snow showers (slight)",
    86: "Snow showers (heavy)",
    95: "Thunderstorm",
    96: "Thunderstorm w/ slight hail",
    99: "Thunderstorm w/ heavy hail",
}


def _fetch_json(url: str, headers: Dict[str, str] | None = None) -> Dict[str, Any]:
    req = Request(url, headers=headers or {"User-Agent": "OpenWebUI-Weather/1.0"})
    with urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def _geocode_zip(zip_code: str) -> Tuple[float, float, str]:
    """Return (lat, lon, pretty_place) for a US ZIP using Zippopotam.us."""
    z = str(zip_code).strip()
    data = _fetch_json(ZIP_BASE + z)
    places = data.get("places", [])
    if not places:
        raise ValueError(f"Couldn't resolve ZIP {z}.")
    p = places[0]
    lat = float(p["latitude"])
    lon = float(p["longitude"])
    pretty = f'{p.get("place name")}, {p.get("state abbreviation")} {z}'
    return lat, lon, pretty


def _openmeteo_current(lat: float, lon: float) -> Dict[str, Any]:
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": ",".join(
            [
                "temperature_2m",
                "apparent_temperature",
                "relative_humidity_2m",
                "wind_speed_10m",
                "wind_direction_10m",
                "precipitation",
                "weather_code",
            ]
        ),
        "temperature_unit": "fahrenheit",
        "windspeed_unit": "mph",
        "precipitation_unit": "inch",
        "timezone": "auto",
    }
    return _fetch_json(OPENMETEO + "?" + urlencode(params))


def _openmeteo_current_and_daily(lat: float, lon: float, days: int) -> Dict[str, Any]:
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": ",".join(
            [
                "temperature_2m",
                "apparent_temperature",
                "relative_humidity_2m",
                "wind_speed_10m",
                "wind_direction_10m",
                "precipitation",
                "weather_code",
            ]
        ),
        "daily": ",".join(
            [
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_probability_max",
                "weather_code",
            ]
        ),
        "forecast_days": max(1, min(int(days), 7)),
        "temperature_unit": "fahrenheit",
        "windspeed_unit": "mph",
        "precipitation_unit": "inch",
        "timezone": "auto",
    }
    return _fetch_json(OPENMETEO + "?" + urlencode(params))


def _fmt_dir(deg: Any) -> str:
    try:
        d = float(deg)
    except Exception:
        return f"{deg}°"
    dirs = [
        "N",
        "NNE",
        "NE",
        "ENE",
        "E",
        "ESE",
        "SE",
        "SSE",
        "S",
        "SSW",
        "SW",
        "WSW",
        "W",
        "WNW",
        "NW",
        "NNW",
    ]
    idx = int((d % 360) / 22.5 + 0.5) % 16
    return f"{dirs[idx]} ({int(round(d))}°)"


class Tools:
    """
    Two simple, callable tools:

    - weather(zip_code: str) -> str
      Current weather for a US ZIP (imperial units).

    - weather_forecast(zip_code: str, days: int = 3) -> str
      Current + next N days (1–7) daily forecast in imperial units.

    Usage prompts (examples):
      - "Use weather for 10001"
      - "Use weather_forecast for 94105"
      - "Use weather_forecast for 73301 with 5 days"
    """

    def weather(self, zip_code: str) -> str:
        """
        Get current weather for a US ZIP code (imperial units).
        :param zip_code: ZIP code string, e.g., "10001"
        :return: Human-readable current conditions
        """
        try:
            lat, lon, place = _geocode_zip(zip_code)
            data = _openmeteo_current(lat, lon)
            cur = data.get("current", {})
            tz = data.get("timezone", "local")
            code = cur.get("weather_code")
            desc = WMO_MAP.get(int(code) if code is not None else -1, f"Code {code}")
            temp = cur.get("temperature_2m")
            feels = cur.get("apparent_temperature")
            rh = cur.get("relative_humidity_2m")
            wind_spd = cur.get("wind_speed_10m")
            wind_dir = cur.get("wind_direction_10m")
            precip = cur.get("precipitation")
            t_iso = cur.get("time")
            when = t_iso if not t_iso else f"{t_iso} ({tz})"

            return (
                f"Current weather for {place}\n"
                f"• Conditions: {desc}\n"
                f"• Temperature: {temp} °F (feels like {feels} °F)\n"
                f"• Humidity: {rh}%\n"
                f"• Wind: {wind_spd} mph {_fmt_dir(wind_dir)}\n"
                f"• Precip (last hour): {precip} in\n"
                f"• As of: {when}\n"
                f"Source: Open-Meteo (no API key) · Geocode: Zippopotam.us"
            )
        except Exception as e:
            return f"Sorry, I couldn't get the weather for ZIP '{zip_code}'. ({e})"

    def weather_forecast(self, zip_code: str, days: int = 3) -> str:
        """
        Current weather + up to 7-day daily forecast for a US ZIP (imperial units).
        :param zip_code: ZIP code string, e.g., "94105"
        :param days: Number of forecast days (1–7). Default 3.
        :return: Human-readable current + forecast
        """
        try:
            lat, lon, place = _geocode_zip(zip_code)
            data = _openmeteo_current_and_daily(lat, lon, days)
            cur = data.get("current", {})
            tz = data.get("timezone", "local")
            code = cur.get("weather_code")
            desc = WMO_MAP.get(int(code) if code is not None else -1, f"Code {code}")
            temp = cur.get("temperature_2m")
            feels = cur.get("apparent_temperature")
            rh = cur.get("relative_humidity_2m")
            wind_spd = cur.get("wind_speed_10m")
            wind_dir = cur.get("wind_direction_10m")
            precip = cur.get("precipitation")
            t_iso = cur.get("time")
            when = t_iso if not t_iso else f"{t_iso} ({tz})"

            # Daily block
            daily = data.get("daily", {})
            dates = daily.get("time", []) or []
            tmax = daily.get("temperature_2m_max", []) or []
            tmin = daily.get("temperature_2m_min", []) or []
            popmax = daily.get("precipitation_probability_max", []) or []
            codes = daily.get("weather_code", []) or []
            n = min(len(dates), max(1, min(int(days), 7)))

            lines = []
            for i in range(n):
                dt = dates[i]
                try:
                    wd = datetime.date.fromisoformat(dt).strftime("%a")
                except Exception:
                    wd = dt
                code_i = codes[i] if i < len(codes) else None
                dsc = WMO_MAP.get(
                    int(code_i) if code_i is not None else -1, f"Code {code_i}"
                )
                tmax_i = tmax[i] if i < len(tmax) else "—"
                tmin_i = tmin[i] if i < len(tmin) else "—"
                pop_i = popmax[i] if i < len(popmax) else "—"
                lines.append(
                    f"{wd} {dt}: {dsc}; High {tmax_i} °F / Low {tmin_i} °F; POP(max) {pop_i}%"
                )

            forecast_block = (
                "\n".join("• " + ln for ln in lines) if lines else "• (No daily data)"
            )

            return (
                f"Weather for {place}\n"
                f"— Current —\n"
                f"• Conditions: {desc}\n"
                f"• Temperature: {temp} °F (feels like {feels} °F)\n"
                f"• Humidity: {rh}%\n"
                f"• Wind: {wind_spd} mph {_fmt_dir(wind_dir)}\n"
                f"• Precip (last hour): {precip} in\n"
                f"• As of: {when}\n\n"
                f"— Forecast (next {n} day(s)) —\n"
                f"{forecast_block}\n\n"
                f"Source: Open-Meteo (no API key) · Geocode: Zippopotam.us"
            )
        except Exception as e:
            return f"Sorry, I couldn't get the forecast for ZIP '{zip_code}'. ({e})"