import hashlib
from django.conf import settings
from django.core.cache import cache
from .external import resolve_location, get_route
from .stations import get_index
from .planner import plan_fuel_stops
import time 


def build_plan(start_text, finish_text):
    key = "plan:" + hashlib.md5(f"{start_text.strip().lower()}|{finish_text.strip().lower()}".encode()).hexdigest()
    if (hit := cache.get(key)) is not None:
        return hit

    start, finish = resolve_location(start_text), resolve_location(finish_text)
    miles, coords = get_route(start, finish)
    nodes = get_index().along_route(coords, miles, settings.CORRIDOR_MILES)
    purchases = plan_fuel_stops(miles, nodes, settings.VEHICLE_RANGE_MILES, settings.VEHICLE_MPG)

    stops = [{
        "name": p.node.station["name"], "address": p.node.station["address"],
        "city": p.node.station["city"], "state": p.node.station["state"],
        "lat": p.node.station["lat"], "lng": p.node.station["lng"],
        "mile_marker": round(p.node.mile, 1), "price_per_gallon": round(p.node.price, 3),
        "gallons": round(p.gallons, 2), "cost": round(p.cost, 2),
    } for p in purchases]

    step = max(1, len(coords) // 1500)  # thin geometry for the response
    line = coords[::step] + ([coords[-1]] if (len(coords) - 1) % step else [])

    result = {
        "start": {"query": start_text, "lat": start[0], "lng": start[1]},
        "finish": {"query": finish_text, "lat": finish[0], "lng": finish[1]},
        "distance_miles": round(miles, 1),
        "vehicle": {"range_miles": settings.VEHICLE_RANGE_MILES, "mpg": settings.VEHICLE_MPG},
        "fuel_stops": stops,
        "total_gallons_purchased": round(sum(s["gallons"] for s in stops), 2),
        "total_fuel_cost": round(sum(s["cost"] for s in stops), 2),
        "route": {"type": "Feature", "properties": {},
                  "geometry": {"type": "LineString", "coordinates": line}},
    }
    cache.set(key, result, 3600)
    return result