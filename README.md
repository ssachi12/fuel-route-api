# Fuel Route API

A Django API that takes a **start** and **finish** location in the contiguous USA and returns:

- the driving route as GeoJSON (ready to draw on any map),
- the **cost-optimal fuel stops** along the route, using the provided fuel price file,
- the **total money spent on fuel**.

Vehicle assumptions: **500-mile maximum range** and **10 miles per gallon**.

---

## Quick start

Requires Python 3.12+.

```bash
git clone https://github.com/ssachi12/fuel-route-api.git
cd fuel-route-api

python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python manage.py migrate
python manage.py loaddata data/stations_fixture.json   # pre-geocoded stations, no downloads needed
python manage.py runserver
```

Then call the API:

```
GET http://127.0.0.1:8000/api/route/?start=New York, NY&finish=Los Angeles, CA
```

Django is pinned in `requirements.txt` (latest stable release at the time of writing).

---

## API

### `GET /api/route/`

| Query parameter | Required | Description |
|---|---|---|
| `start` | yes | Place name (e.g. `Austin, TX`) or coordinates (`30.27,-97.74`) |
| `finish` | yes | Place name or coordinates |

Both locations must be inside the contiguous USA.

### Example response (trimmed)

```json
{
  "start":  { "query": "New York, NY",    "lat": 40.7127281, "lng": -74.0060152 },
  "finish": { "query": "Los Angeles, CA", "lat": 34.0536923, "lng": -118.2427676 },
  "distance_miles": 2794,
  "vehicle": { "range_miles": 500, "mpg": 10 },
  "fuel_stops": [
    {
      "name": "SHEETZ #639",
      "address": "I-80 Exit 223",
      "city": "Youngstown",
      "state": "OH",
      "lat": 41.09978,
      "lng": -80.64952,
      "mile_marker": 390.8,
      "price_per_gallon": 3.059,
      "gallons": 35.94,
      "cost": 109.93
    }
  ],
  "total_gallons_purchased": 229.39,
  "total_fuel_cost": 707.42,
  "route": {
    "type": "Feature",
    "properties": {},
    "geometry": { "type": "LineString", "coordinates": [[-74.0057, 40.7121], "..."] }
  },
  "map_url": "http://127.0.0.1:8000/api/route/map/?start=New+York%2C+NY&finish=Los+Angeles%2C+CA"
}
```

| Field | Meaning |
|---|---|
| `distance_miles` | Total driving distance from the routing service |
| `fuel_stops[].mile_marker` | Distance along the route at which the stop occurs |
| `fuel_stops[].gallons` / `cost` | Fuel bought at that stop and what it costs |
| `total_gallons_purchased` | Sum of gallons bought at the stops |
| `total_fuel_cost` | Total money spent on fuel (sum of the stop costs) |
| `route` | GeoJSON LineString of the route. Paste it into [geojson.io](https://geojson.io) or load it in any map library |
| `map_url` | Optional convenience page that draws the route and stops on a Leaflet map |

### Errors

Errors are returned as JSON: `{"error": "..."}`

| Status | When |
|---|---|
| 400 | Missing parameter, location not found, or outside the contiguous USA |
| 422 | No fuel station within range on part of the route (trip cannot be completed) |
| 502 | The routing or geocoding service failed |

---

## How it works

1. **Routing (1 external call).** The route comes from the free **OSRM** public server, which returns the distance and the full road geometry in a single request.
2. **Geocoding (0 to 2 external calls).** Place names are resolved with the free **Nominatim** service and cached. Passing `lat,lng` skips geocoding completely.
3. **Fuel stations (0 external calls at request time).** The provided CSV is imported once. Canadian rows are dropped, duplicate truckstop IDs are collapsed to their lowest price, and each station gets a city-level coordinate from the free **GeoNames** dataset. No geocoding happens while serving a request.
4. **Stations along the route (milliseconds).** A KD-tree (`scipy`) over the route points finds every station within **5 miles** of the route and gives it a mile marker.
5. **Choosing stops.** A cheapest-fuel greedy algorithm (see below).
6. **Caching.** Finished plans are cached for an hour, so repeating a request costs no external calls and returns almost instantly.

### External API calls per request

| Request type | OSRM | Nominatim | Total |
|---|---|---|---|
| Place names, first time | 1 | 2 | 3 |
| Coordinates (`lat,lng`) | 1 | 0 | 1 |
| Same request repeated (cached) | 0 | 0 | 0 |

### The fuel stop algorithm

The vehicle starts with a full tank. From the current position the planner looks at every station reachable on a full tank (500 miles):

- If a station that is **cheaper by more than `MIN_SAVINGS` (5 cents/gal)** is within range, it buys **only enough fuel to reach it**.
- Otherwise it **fills the tank** here and continues to the **farthest** station within 5 cents of the cheapest price in range.
- The destination is treated as a station priced at $0, so the planner never buys more fuel than the trip needs.

This is the classic cheapest-gas-station strategy: optimal when each station has a single price. The 5-cent tolerance is deliberate. Without it the plan makes extra stops that save only fractions of a cent per gallon (for New York to Los Angeles it cut the plan from 13 stops to 7 for about $2.69 more in total fuel cost). It is a single constant (`MIN_SAVINGS` in `routeplanner/services/planner.py`).

**Sanity check built into the numbers:** because the car starts full, total gallons purchased must equal `(distance - 500) / 10`. For New York to Los Angeles that is `(2794 - 500) / 10 = 229.4`, and the API returns `229.39` (the difference is rounding to two decimals per stop).

---

## Assumptions and limitations

- **Full starting tank.** The vehicle starts with a full 500-mile tank that is not charged to the trip, so `total_fuel_cost` is the cost of fuel purchased en route. For trips of 500 miles or less, no stops are needed and the cost is $0.
- **City-level station coordinates.** The price file has no latitude or longitude, only city and state. Stations are placed at their city's location and matched within 5 miles of the route, so mile markers are approximate.
- **No detour cost.** Fuel used to leave the highway for a station is ignored.
- **No safety margin.** Legs may use nearly the full 500-mile range (the planner uses the exact maximum range you set).
- **Fuel price data is static.** Prices come from the supplied file. The lowest price per truckstop ID is used when the file lists several.
- **Contiguous USA only.** Alaska and Hawaii are rejected.
- **OSRM demo server.** The public OSRM server is fine for this project but is not intended for heavy production traffic.

---

## Project structure

```
config/                         Django project settings and root URLs
routeplanner/
  models.py                     Station model
  views.py                      GET /api/route/ (JSON) and optional map page
  urls.py
  services/
    external.py                 OSRM routing + Nominatim geocoding (the only external calls)
    geo.py                      distance / KD-tree coordinate helpers
    stations.py                 loads stations, finds those along the route
    planner.py                  fuel stop algorithm
    trip.py                     orchestrates a request and caches the result
  management/commands/
    import_fuel_prices.py       CSV import + offline geocoding
  templates/routeplanner/map.html   optional Leaflet map
  tests.py
data/
  fuel-prices-for-be-assessment.csv   original price file
  stations_fixture.json               pre-geocoded stations (used by loaddata)
```

---

## Settings

In `config/settings.py`:

| Setting | Default | Meaning |
|---|---|---|
| `VEHICLE_RANGE_MILES` | 500 | Maximum range on a full tank |
| `VEHICLE_MPG` | 10 | Fuel economy |
| `CORRIDOR_MILES` | 5 | Maximum distance of a station from the route |
| `USER_AGENT` | project string | Sent to Nominatim (required by its usage policy) |

`MIN_SAVINGS` (5 cents per gallon) lives in `routeplanner/services/planner.py`.

---

## Re-importing the fuel prices (optional)

The repository already contains `data/stations_fixture.json`, so this is only needed to rebuild it from the original CSV.

1. Download `cities1000.zip` from <https://download.geonames.org/export/dump/> and unzip it to get `cities1000.txt`.
2. Run:

```bash
python manage.py import_fuel_prices data/fuel-prices-for-be-assessment.csv --cities cities1000.txt
python manage.py dumpdata routeplanner > data/stations_fixture.json
```

The command filters out non-US rows, keeps the lowest price per truckstop, and prints how many stations were imported and how many could not be given coordinates.

---

## Tests

```bash
python manage.py test
```

The tests cover the planner: no stops for short trips, buying where fuel is cheaper with total gallons equal to `(distance - range) / mpg`, and a clear error when there is a gap larger than the vehicle's range.

---

## Possible improvements

- Geocode full station addresses (street and exit) for exact positions instead of city-level.
- Account for the detour distance to each station.
- Add a configurable safety buffer on the range.
- Use a shared cache (Redis) and a self-hosted routing engine for production traffic.
- Refresh fuel prices from a live source.
