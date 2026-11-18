PREFIXES = {"st": "saint", "ste": "sainte", "ft": "fort", "mt": "mount"}
ALIASES = {"new york": "new york city", "nyc": "new york city"}

def norm_city(name):
    """Lowercase, collapse spaces, drop periods, expand St./Ft./Mt."""
    words = name.replace(".", " ").lower().split()
    if words and words[0] in PREFIXES:
        words[0] = PREFIXES[words[0]]
    return " ".join(words)