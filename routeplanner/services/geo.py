import numpy as np

EARTH_MI = 3958.7613

def haversine_mi(lat1, lng1, lat2, lng2):
    lat1, lng1, lat2, lng2 = map(np.radians, (lat1, lng1, lat2, lng2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lng2 - lng1) / 2) ** 2
    return 2 * EARTH_MI * np.arcsin(np.sqrt(a))

def to_xyz(lat, lng):
    la, lo = np.radians(lat), np.radians(lng)
    return np.column_stack((np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)))

def miles_to_chord(mi):
    return 2 * np.sin(mi / (2 * EARTH_MI))