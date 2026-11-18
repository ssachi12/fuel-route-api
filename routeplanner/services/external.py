import re
import requests
from django.conf import settings
from django.core.cache import cache

_session = requests.Session()
LATLNG = re.compile(r"^\s*(-?\d+(\.\d+)?)\s*,\s*(-?\d+(\.\d+)?)\s*$")


class LocationError(Exception): ...
class RoutingError(Exception): ...


def resolve_location(text):
    """'lat,lng' -> no network. Otherwise Nominatim, cached for a day."""
    if m := LATLNG.match(text):
        lat, lng = float(m[1]), float(m[3])
    else:
        key = "geo:" + text.strip().lower()
        hit = cache.get(key)
        if hit is None:
            r = _session.get("https://nominatim.openstreetmap.org/search",
                             params={"q": text, "format": "jsonv2", "limit": 1, "countrycodes": "us"},
                             headers={"User-Agent": settings.USER_AGENT}, timeout=10)
            r.raise_for_status()
            data = r.json()
            if not data:
                raise LocationError(f"Could not find a US location for '{text}'")
            hit = (float(data[0]["lat"]), float(data[0]["lon"]))
            cache.set(key, hit, 86400)
        lat, lng = hit
    if not (24 <= lat <= 50 and -125 <= lng <= -66):
        raise LocationError(f"'{text}' is outside the contiguous USA")
    return lat, lng


def get_route(start, finish):
    """ONE OSRM call -> (distance_miles, [[lng, lat], ...])"""
    coords = f"{start[1]},{start[0]};{finish[1]},{finish[0]}"
    r = _session.get(f"https://router.project-osrm.org/route/v1/driving/{coords}",
                     params={"overview": "full", "geometries": "geojson"}, timeout=20)
    r.raise_for_status()
    data = r.json()
    if data.get("code") != "Ok":
        raise RoutingError(data.get("message", "No route found"))
    route = data["routes"][0]
    return route["distance"] / 1609.344, route["geometry"]["coordinates"]