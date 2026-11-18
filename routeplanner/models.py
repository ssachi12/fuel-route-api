from django.db import models

class Station(models.Model):
    opis_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=300, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2)
    price = models.DecimalField(max_digits=6, decimal_places=3)
    lat = models.FloatField(null=True)
    lng = models.FloatField(null=True)
    
class City(models.Model):
    name = models.CharField(max_length=100)   # normalized
    state = models.CharField(max_length=2)
    lat = models.FloatField()
    lng = models.FloatField()

    class Meta:
        indexes = [models.Index(fields=["name", "state"])]    