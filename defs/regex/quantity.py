import re
from defs.regex_lib import NUMBER_RANGE_STR, build_alternation
from defs.labels import LABELS

UNITS_STRICT = [
    "barrels",
    "bbl",
    "bbl/d",
    "btu",
    "gj",
    "mmbtu",
    "mmbtu/h",
    "mwh",
    "bushels",
    "cwt",
    "hundredweights",
    "pecks",
    "ounces",
    "pounds",
    "tons",
    "tonne",
    "long tons",
    "short tons",
    "joules",
    "gigajoules",
    "mcf",
    "mmcf",
    "bcf",
    "therm",
    "therms",
    "dth",
    "dekatherms",
]
UNITS = [
    "units",
    "items",
    "packages",
    "containers",
    "loads",
    "gallons",
    "gal",
    "liters",
    "ltr",
    "cubic meters",
    "m3",
    "cubic feet",
    "ft3",
    "hectoliters",
    "hL",
    "kiloliters",
    "kL",
    "megaliters",
    "ML",
    "gigaliters",
    "GL",
    "board foot",
    "bf",
    "sheets",
    "coils",
    "bundles",
    "pallets",
    "sacks",
    "bales",
    "heads",
    "carats",
    "ingots",
    "bars",
] + UNITS_STRICT

UNITS_AREA = [
    "square feet",
    "sq ft",
    "sf",
    "square meters",
    "sq m",
    "m2",
    "square miles",
    "sq mi",
    "square kilometers",
    "sq km",
    "km2",
    "acres",
    "hectares",
    "ha",
    "square yards",
    "sq yd",
]

UNITS_LENGTH = [
    "feet",
    "ft",
    "meters",
    "miles",
    "mi",
    "kilometers",
    "km",
    "yards",
    "yd",
    "inches",
    "in",
    "centimeters",
    "cm",
    "millimeters",
    "mm",
    "nautical miles",
    "nm",
]

UNITS_POWER = [
    "watts",
    "kilowatts",
    "kw",
    "megawatts",
    "mw",
    "gigawatts",
    "gw",
    "kilowatt-hours",
    "kwh",
    "megawatt-hours",
    "mwh",
    "horsepower",
    "hp",
    "volt",
    "volts",
    "ampere",
    "amperes",
    "amps",
    "kilovolt",
    "kilovolts",
    "kv",
]

UNITS_DATA = [
    "bytes",
    "kilobytes",
    "kb",
    "megabytes",
    "mb",
    "gigabytes",
    "gb",
    "terabytes",
    "tb",
    "petabytes",
    "pb",
]

UNITS_GENERIC = [
    # Counts
    "pieces",
    "parts",
    "components",
    "elements",
    "slots",
    "seats",
    "positions",
    "spaces",
    "trips",
    "visits",
    "calls",
    "transactions",
    "orders",
    "shipments",
    "deliveries",
    # Financial
    "basis points",
    "bps",
    "lots",
    "tranches",
]

UNITS = (
    UNITS_AREA
    + UNITS_LENGTH
    + UNITS_POWER
    + UNITS_DATA
    + UNITS_GENERIC
    + UNITS_STRICT
)

_UNIT_PATTERN = build_alternation(UNITS)
QUANTITY_REGEX = re.compile(
    rf"\b({NUMBER_RANGE_STR})\s+(?:{_UNIT_PATTERN})\b", re.IGNORECASE
)


def extract_spans(text: str) -> list[tuple[int, int, str]]:
    """
    Extract QUANTITY spans from text.
    Returns (start, end, label) tuples.
    """
    if not text:
        return []
    return [(m.start(), m.end(), LABELS.QUANTITY.value) for m in QUANTITY_REGEX.finditer(text)]
