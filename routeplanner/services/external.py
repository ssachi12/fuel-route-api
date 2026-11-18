import re

import polyline         
import requests
from django.conf import settings
from django.core.cache import cache

from routeplanner.models import City
from .names import norm_city

_session = requests.Session()
LATLNG = re.compile(r"^\s*(-?\d+(\.\d+)?)\s*,\s*(-?\d+(\.\d+)?)\s*$")
CITY_STATE = re.compile(r"^\s*([^,]+?)\s*,\s*([A-Za-z]{2})\s*$")


class LocationError(Exception): ...
class RoutingError(Exception): ...


def _lookup_city(text):
    """'Austin, TX' -> local database lookup, no network."""
    m = CITY_STATE.match(text)
    if not m:
        return None
    c = City.objects.filter(name=norm_city(m[1]), state=m[2].upper()).first()
    return (c.lat, c.lng) if c else None


def _nominatim(text):
    """Fallback for full addresses or unusual names; cached for a day."""
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
    return hit


def resolve_location(text):
    if m := LATLNG.match(text):
        lat, lng = float(m[1]), float(m[3])
    else:
        lat, lng = _lookup_city(text) or _nominatim(text)
    if not (24 <= lat <= 50 and -125 <= lng <= -66):
        raise LocationError(f"'{text}' is outside the contiguous USA")
    return lat, lng


def get_route(start, finish):
    """ONE OSRM call -> (distance_miles, [(lng, lat), ...])"""
    coords = f"{start[1]},{start[0]};{finish[1]},{finish[0]}"
    r = _session.get(f"https://router.project-osrm.org/route/v1/driving/{coords}",
                     params={"overview": "full", "geometries": "polyline6"}, timeout=20)
    r.raise_for_status()
    data = r.json()
    if data.get("code") != "Ok":
        raise RoutingError(data.get("message", "No route found"))
    route = data["routes"][0]
    line = polyline.decode(route["geometry"], 6, geojson=True)   # (lng, lat) pairs
    return route["distance"] / 1609.344, line