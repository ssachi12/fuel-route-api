from django.core.management.base import BaseCommand
from django.db import transaction

from routeplanner.models import City
from .import_fuel_prices import load_cities


class Command(BaseCommand):
    help = "Load GeoNames US cities so place names resolve without calling a geocoding API"

    def add_arguments(self, parser):
        parser.add_argument("cities_path", help="Path to GeoNames cities1000.txt")

    def handle(self, *args, **opts):
        cities = load_cities(opts["cities_path"])
        with transaction.atomic():
            City.objects.all().delete()
            City.objects.bulk_create(
                [City(name=n, state=s, lat=la, lng=lo) for (n, s), (la, lo) in cities.items()],
                batch_size=2000,
            )
        self.stdout.write(self.style.SUCCESS(f"{len(cities)} cities imported"))