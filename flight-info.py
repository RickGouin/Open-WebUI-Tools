"""
title: Open-WebUI Flight Info
author: Rick Gouin
author_url: https://rickgouin.com
version: 1.0
license: GPL v3
description: Fetch flight info by flight number
usage: USE FLIGHT [flight number]
"""

from __future__ import annotations
import json, re, time, typing as t
import urllib.request, urllib.parse, urllib.error

# --------------------------- Utilities ---------------------------------


def _clean(s: t.Optional[str]) -> str:
    return re.sub(r"\s+", "", s or "").upper()


# Common IATA -> ICAO mapping so "DL2206" also tries "DAL2206"
_IATA_ICAO = {
    "AA": "AAL",
    "UA": "UAL",
    "DL": "DAL",
    "WN": "SWA",
    "AS": "ASA",
    "B6": "JBU",
    "F9": "FFT",
    "NK": "NKS",
    "HA": "HAL",
    "BA": "BAW",
    "AF": "AFR",
    "KL": "KLM",
    "LH": "DLH",
    "LX": "SWR",
    "OS": "AUA",
    "IB": "IBE",
    "AZ": "ITA",
    "SK": "SAS",
    "DY": "NAX",
    "QF": "QFA",
    "NZ": "ANZ",
    "VA": "VOZ",
    "AC": "ACA",
    "WS": "WJA",
    "TK": "THY",
    "QR": "QTR",
    "EK": "UAE",
    "EY": "ETD",
    "SV": "SVA",
    "AI": "AIC",
    "JL": "JAL",
    "NH": "ANA",
    "KE": "KAL",
    "OZ": "AAR",
    "CX": "CPA",
    "SQ": "SIA",
    "MH": "MAS",
    "BR": "EVA",
    "TG": "THA",
    "CA": "CCA",
    "MU": "CES",
    "CZ": "CSN",
    "FM": "CSH",
    "VS": "VIR",
    "U2": "EZY",
    "FR": "RYR",
    "W6": "WZZ",
}


def _candidates(user: str) -> list[str]:
    s = _clean(user)
    out = {s}
    m = re.match(r"^([A-Z0-9]{2})(\d{1,4}[A-Z]?)$", s)
    if m and m.group(1) in _IATA_ICAO:
        out.add(_IATA_ICAO[m.group(1)] + m.group(2))
    return list(out)


def _map_link(lat: float | None, lon: float | None) -> str | None:
    if lat is None or lon is None:
        return None
    return f"https://www.openstreetmap.org/?mlat={lat:.4f}&mlon={lon:.4f}#map=9/{lat:.4f}/{lon:.4f}"


def _fetch_json(url: str, timeout: int = 12) -> dict:
    req = urllib.request.Request(
        url, headers={"User-Agent": "OpenWebUI-Flight-Tool/2.0"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

_PROVIDERS = [
    "https://api.airplanes.live/v2",
    "http://api.airplanes.live/v2",  # in case https is transient
    "https://api.adsb.one/v2",
    "https://api.adsb.lol/v2",
]


def _query_callsign(base: str, callsign: str) -> dict | None:
    url = f"{base}/callsign/{urllib.parse.quote(callsign)}"
    try:
        data = _fetch_json(url)
    except Exception:
        return None
    ac = (data or {}).get("ac") or []
    if not ac:
        return None

    # Choose the freshest aircraft object (lowest "seen" seconds)
    best = min(ac, key=lambda a: a.get("seen", 9e9))

    lat = best.get("lat")
    lon = best.get("lon")

    if (lat is None or lon is None) and isinstance(best.get("lastPosition"), dict):
        lat = best["lastPosition"].get("lat", lat)
        lon = best["lastPosition"].get("lon", lon)

    return {
        "source": base,
        "flight": _clean(best.get("flight")),
        "hex": best.get("hex"),
        "lat": lat,
        "lon": lon,
        "altitude_ft": best.get("alt_geom") or best.get("alt_baro"),
        "speed_kt": best.get("gs"),
        "heading_deg": best.get("track"),
        "vertical_rate_fpm": best.get("baro_rate"),
        "squawk": best.get("squawk"),
        "seen_s": best.get("seen"),
        "category": best.get("category"),
    }

class Tools:
    """
    Call with: use_flight("DL2206")
    Natural language trigger: "Use Flight DL2206"
    """

    class Valves:
        include_map_link: bool = True

    def __init__(self):
        self.valves = self.Valves()
        self.citation = False  # Return plain JSON

    def use_flight(self, flight_number: str) -> dict:
        if not flight_number or not flight_number.strip():
            return {
                "ok": False,
                "error": "Please provide a flight number (e.g., 'DL2206').",
            }

        # Build candidate callsigns (IATA + possible ICAO)
        cands = _candidates(flight_number)

        best = None
        for provider in _PROVIDERS:
            for cs in cands:
                res = _query_callsign(provider, cs)
                if res:
                    if (best is None) or (
                        res.get("seen_s", 9e9) < best.get("seen_s", 9e9)
                    ):
                        best = res
            if best:  # stop at first provider that yielded a match
                break

        if best is None:
            return {
                "ok": False,
                "error": f"No live ADS-B match for '{flight_number}'. It may be on the ground/out of coverage or using a different callsign (try ICAO like DAL2206 for Delta).",
            }

        out = {
            "ok": True,
            "source": best["source"],
            "queried_at_unix": int(time.time()),
            "callsign": best["flight"],
            "hex": best["hex"],
            "position": {
                "lat": best["lat"],
                "lon": best["lon"],
                "stale_seconds": best.get("seen_s"),
            },
            "altitude_ft": best["altitude_ft"],
            "speed_kt": best["speed_kt"],
            "heading_deg": best["heading_deg"],
            "vertical_rate_fpm": best["vertical_rate_fpm"],
            "on_ground": (best.get("gs") or 0) < 40
            and (best.get("altitude_ft") or 0) < 2500,
            "squawk": best.get("squawk"),
            "category": best.get("category"),
        }

        link = (
            _map_link(best["lat"], best["lon"])
            if self.valves.include_map_link
            else None
        )
        if link:
            out["map"] = link
        return out