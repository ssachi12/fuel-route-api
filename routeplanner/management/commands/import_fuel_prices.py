import csv
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand
from django.db import transaction

from routeplanner.models import Station

US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY",
    "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND",
    "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
}

# Common abbreviations in the price file vs. the full words GeoNames uses
PREFIXES = {"st": "saint", "ste": "sainte", "ft": "fort", "mt": "mount"}


def norm_city(name):
    """Lowercase, collapse spaces, drop periods, expand St./Ft./Mt. so both files compare equal."""
    words = name.replace(".", " ").lower().split()
    if words and words[0] in PREFIXES:
        words[0] = PREFIXES[words[0]]
    return " ".join(words)


def load_cities(path):
    """GeoNames cities file -> {(normalized city, state): (lat, lng)}, keeping the most populous match."""
    best = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            c = line.rstrip("\n").split("\t")
            if len(c) < 15 or c[8] != "US":
                continue
            lat, lng, state, pop = float(c[4]), float(c[5]), c[10], int(c[14] or 0)
            for name in {c[1], c[2]}:  # name and ascii name
                key = (norm_city(name), state)
                if key not in best or pop > best[key][2]:
                    best[key] = (lat, lng, pop)
    return {k: (v[0], v[1]) for k, v in best.items()}


class Command(BaseCommand):
    help = "Import the fuel prices CSV (US stations only) and attach city-level coordinates"

    def add_arguments(self, parser):
        parser.add_argument("csv_path", help="Path to the fuel prices CSV")
        parser.add_argument("--cities", required=True, help="Path to GeoNames cities1000.txt")

    def handle(self, *args, **opts):
        cities = load_cities(opts["cities"])
        self.stdout.write(f"Loaded {len(cities)} US city names from GeoNames")

        cheapest = {}      # one row per truckstop ID: keep the lowest price
        skipped_non_us = 0

        with open(opts["csv_path"], newline="", encoding="utf-8-sig") as f:
            for raw in csv.DictReader(f):
                r = {k.strip(): (v or "").strip() for k, v in raw.items()}
                if r["State"].upper() not in US_STATES:
                    skipped_non_us += 1          # drops the Canadian rows
                    continue
                try:
                    oid = int(r["OPIS Truckstop ID"])
                    price = Decimal(r["Retail Price"])
                except (ValueError, InvalidOperation):
                    continue
                if oid not in cheapest or price < cheapest[oid]["price"]:
                    cheapest[oid] = {
                        "price": price,
                        "name": r["Truckstop Name"],
                        "address": r["Address"],
                        "city": " ".join(r["City"].split()),
                        "state": r["State"].upper(),
                    }

        objs, missed = [], []
        for oid, d in cheapest.items():
            coord = cities.get((norm_city(d["city"]), d["state"]))
            if not coord:
                missed.append(f'{d["city"]}, {d["state"]}')
            objs.append(Station(
                opis_id=oid,
                lat=coord[0] if coord else None,
                lng=coord[1] if coord else None,
                **d,
            ))

        with transaction.atomic():
            Station.objects.all().delete()   # clean re-import, no leftover Canadian rows
            Station.objects.bulk_create(objs)

        self.stdout.write(self.style.SUCCESS(
            f"{len(objs)} US stations imported "
            f"({skipped_non_us} non-US rows skipped, {len(missed)} without coordinates)"
        ))
        if missed:
            self.stdout.write("Sample of cities with no match: " + "; ".join(sorted(set(missed))[:15]))