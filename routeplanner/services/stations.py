from functools import lru_cache
import numpy as np
from scipy.spatial import cKDTree
from routeplanner.models import Station
from .geo import to_xyz, miles_to_chord, haversine_mi
from .planner import Node


class StationIndex:
    def __init__(self):
        self.rows = list(Station.objects.filter(lat__isnull=False).values(
            "name", "address", "city", "state", "price", "lat", "lng"))
        for r in self.rows:
            r["price"] = float(r["price"])
        self.xyz = to_xyz(np.array([r["lat"] for r in self.rows]), np.array([r["lng"] for r in self.rows]))

    def along_route(self, coords, total_miles, corridor_mi):
        arr = np.asarray(coords)
        lng, lat = arr[:, 0], arr[:, 1]
        seg = haversine_mi(lat[:-1], lng[:-1], lat[1:], lng[1:])
        cum = np.concatenate([[0.0], np.cumsum(seg)])
        cum *= total_miles / cum[-1]  # align with OSRM's own distance
        tree = cKDTree(to_xyz(lat, lng))
        dist, idx = tree.query(self.xyz, distance_upper_bound=miles_to_chord(corridor_mi))
        return [Node(float(cum[idx[i]]), self.rows[i]["price"], self.rows[i])
                for i in np.flatnonzero(np.isfinite(dist))]


@lru_cache(maxsize=1)
def get_index():
    return StationIndex()