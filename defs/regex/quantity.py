# =============================================================================
# SI PREFIXES
# =============================================================================

import re

from defs.labels import LABELS
from defs.regex_lib import NUMBER_RANGE_STR, build_alternation


SI_PREFIXES: dict[str, str] = {
    "kilo": "k",
    "mega": "M",
    "giga": "G",
    "tera": "T",
    "peta": "P",
    "hecto": "h",
    "centi": "c",
    "milli": "m",
    "micro": "μ",
    "nano": "n",
}

# =============================================================================
# SI BASE UNITS
# Each entry defines the base; area/volume are derived automatically.
# =============================================================================

SI_UNITS: dict[str, dict] = {
    "length": {
        "name": "metre",
        "aliases": ["meter"],
        "abbrev": "m",
        "prefixes": ["kilo", "hecto", "centi", "milli"],
        "derive_area": True,  # generates square metre, km2, etc.
        "derive_volume": True,  # generates cubic metre, m3, etc.
    },
    "mass": {
        "name": "gram",
        "aliases": [],
        "abbrev": "g",
        "prefixes": ["kilo", "mega", "milli"],
        "extra": ["tonne", "tonnes", "metric ton", "metric tons"],
    },
    "temperature": {
        "name": "celsius",
        "aliases": [],
        "abbrev": "°C",
        "prefixes": [],
        "extra": ["kelvin", "degrees celsius", "degrees kelvin", "centigrade", "degree centigrade"],
    },
    "volume": {
        "name": "litre",
        "aliases": ["liter"],
        "abbrev": "L",
        "prefixes": ["kilo", "mega", "giga", "milli", "hecto"],
    },
    "energy": {
        "name": "joule",
        "aliases": [],
        "abbrev": "J",
        "prefixes": ["kilo", "mega", "giga"],
    },
    "power": {
        "name": "watt",
        "aliases": [],
        "abbrev": "W",
        "prefixes": ["kilo", "mega", "giga"],
        "compounds": [("hour", "h")],  # kilowatt-hour -> kWh
    },
    "pressure": {
        "name": "pascal",
        "aliases": [],
        "abbrev": "Pa",
        "prefixes": ["kilo", "mega"],
    },
    "electric_current": {
        "name": "ampere",
        "aliases": ["amp"],
        "abbrev": "A",
        "prefixes": ["kilo", "milli"],
    },
    "voltage": {
        "name": "volt",
        "aliases": [],
        "abbrev": "V",
        "prefixes": ["kilo", "mega", "milli"],
    },
    "data": {
        "name": "byte",
        "aliases": ["bit"],
        "abbrev": "B",
        "prefixes": ["kilo", "mega", "giga", "tera", "peta"],
    },
}

# =============================================================================
# IMPERIAL UNITS
# Same dimension keys as SI_UNITS for merging.
# =============================================================================

IMPERIAL_UNITS: dict[str, dict] = {
    "length": {
        "units": [
            {"name": "inch", "plural": "inches", "abbrev": "in"},
            {"name": "foot", "plural": "feet", "abbrev": "ft"},
            {"name": "yard", "plural": "yards", "abbrev": "yd"},
            {"name": "mile", "plural": "miles", "abbrev": "mi"},
            {"name": "nautical mile", "plural": "nautical miles", "abbrev": "nm"},
        ],
        "derive_area": True,
        "derive_volume": True,
    },
    "mass": {
        "units": [
            {"name": "ounce", "plural": "ounces", "abbrev": "oz"},
            {"name": "pound", "plural": "pounds", "abbrev": "lb"},
            {
                "name": "ton",
                "plural": "tons",
                "abbrev": None,
                "extra": ["short ton", "short tons", "long ton", "long tons"],
            },
            {"name": "hundredweight", "plural": "hundredweights", "abbrev": "cwt"},
        ],
    },
    "temperature": {
        "units": [
            {
                "name": "fahrenheit",
                "plural": None,
                "abbrev": "°F",
                "extra": ["degrees fahrenheit"],
            },
        ],
    },
    "volume": {
        "units": [
            {"name": "gallon", "plural": "gallons", "abbrev": "gal"},
            {"name": "quart", "plural": "quarts", "abbrev": "qt"},
            {"name": "pint", "plural": "pints", "abbrev": "pt"},
            {"name": "fluid ounce", "plural": "fluid ounces", "abbrev": "fl oz"},
            {
                "name": "barrel",
                "plural": "barrels",
                "abbrev": "bbl",
                "extra": ["bbl/d"],
            },
            {"name": "bushel", "plural": "bushels", "abbrev": None},
            {"name": "peck", "plural": "pecks", "abbrev": None},
        ],
    },
    "area": {
        "units": [
            {"name": "acre", "plural": "acres", "abbrev": None},
            {"name": "hectare", "plural": "hectares", "abbrev": "ha"},
        ],
    },
    "energy": {
        "units": [
            {
                "name": "btu",
                "plural": None,
                "abbrev": None,
                "extra": ["mmbtu", "mmbtu/h"],
            },
            {"name": "therm", "plural": "therms", "abbrev": None},
            {"name": "dekatherm", "plural": "dekatherms", "abbrev": "dth"},
        ],
    },
    "power": {
        "units": [
            {"name": "horsepower", "plural": None, "abbrev": "hp"},
        ],
    },
    "gas_volume": {
        "units": [
            {"name": "mcf", "plural": None, "abbrev": None},
            {"name": "mmcf", "plural": None, "abbrev": None},
            {"name": "bcf", "plural": None, "abbrev": None},
        ],
    },
}

# =============================================================================
# DERIVED DIMENSION GENERATOR
# Builds area (square X) and volume (cubic X) from a length base.
# =============================================================================


def _derive_area_terms(name: str, aliases: list[str], abbrev: str | None) -> list[str]:
    terms: list[str] = []
    for n in [name] + aliases:
        terms += [f"square {n}", f"sq {n}"]
        if abbrev:
            terms += [f"sq {abbrev}", f"{abbrev}2"]
    return terms


def _derive_volume_terms(
    name: str, aliases: list[str], abbrev: str | None
) -> list[str]:
    terms: list[str] = []
    for n in [name] + aliases:
        terms += [f"cubic {n}", f"cu {n}"]
        if abbrev:
            terms += [f"cu {abbrev}", f"{abbrev}3"]
    return terms


# =============================================================================
# TERM BUILDERS
# =============================================================================


def _build_si_terms(config: dict) -> list[str]:
    terms: list[str] = []
    name = config["name"]
    aliases = config.get("aliases", [])
    abbrev = config.get("abbrev", "")
    prefixes = config.get("prefixes", [])
    compounds = config.get("compounds", [])
    extra = config.get("extra", [])

    # Base forms
    for n in [name] + aliases:
        terms += [n, f"{n}s"]
    if abbrev:
        terms.append(abbrev)

    # Prefixed forms
    for prefix in prefixes:
        si_abbrev = SI_PREFIXES.get(prefix, "")
        for n in [name] + aliases:
            terms += [f"{prefix}{n}", f"{prefix}{n}s"]
        if si_abbrev and abbrev:
            terms.append(f"{si_abbrev}{abbrev}")
            # Compound forms: kilowatt-hour, kWh
            for compound_name, compound_abbrev in compounds:
                terms += [
                    f"{prefix}{name}-{compound_name}",
                    f"{prefix}{name} {compound_name}",
                ]
                if si_abbrev and compound_abbrev:
                    terms.append(f"{si_abbrev}{abbrev}{compound_abbrev}")

    # Derived area/volume
    if config.get("derive_area"):
        terms += _derive_area_terms(name, aliases, abbrev)
        for prefix in prefixes:
            si_abbrev = SI_PREFIXES.get(prefix, "")
            prefixed_name = f"{prefix}{name}"
            terms += _derive_area_terms(
                prefixed_name, [], f"{si_abbrev}{abbrev}" if si_abbrev else None
            )

    if config.get("derive_volume"):
        terms += _derive_volume_terms(name, aliases, abbrev)
        for prefix in prefixes:
            si_abbrev = SI_PREFIXES.get(prefix, "")
            prefixed_name = f"{prefix}{name}"
            terms += _derive_volume_terms(
                prefixed_name, [], f"{si_abbrev}{abbrev}" if si_abbrev else None
            )

    terms += extra
    return terms


def _build_imperial_terms(config: dict) -> list[str]:
    terms: list[str] = []
    derive_area = config.get("derive_area", False)
    derive_volume = config.get("derive_volume", False)

    for unit in config.get("units", []):
        name = unit["name"]
        plural = unit.get("plural")
        abbrev = unit.get("abbrev")
        extra = unit.get("extra", [])

        terms.append(name)
        if plural:
            terms.append(plural)
        if abbrev:
            terms.append(abbrev)
        terms += extra

        if derive_area:
            terms += _derive_area_terms(name, [], abbrev)
            if plural:
                terms += _derive_area_terms(plural, [], None)
        if derive_volume:
            terms += _derive_volume_terms(name, [], abbrev)
            if plural:
                terms += _derive_volume_terms(plural, [], None)

    return terms


# =============================================================================
# MERGE INTO MEGA DICT + FLAT LIST
# =============================================================================


def build_all_units() -> tuple[dict[str, list[str]], list[str]]:
    """
    Returns:
        mega_dict: dimension -> list of all surface forms (SI + imperial)
        flat: deduplicated flat list for regex building
    """
    mega_dict: dict[str, list[str]] = {}

    for dimension, config in SI_UNITS.items():
        mega_dict.setdefault(dimension, [])
        mega_dict[dimension] += _build_si_terms(config)

    for dimension, config in IMPERIAL_UNITS.items():
        mega_dict.setdefault(dimension, [])
        mega_dict[dimension] += _build_imperial_terms(config)

    # Deduplicate per dimension, preserve order
    for dim in mega_dict:
        seen: set[str] = set()
        deduped: list[str] = []
        for t in mega_dict[dim]:
            if t.lower() not in seen:
                seen.add(t.lower())
                deduped.append(t)
        mega_dict[dim] = deduped

    flat = [t for terms in mega_dict.values() for t in terms]
    return mega_dict, flat


UNITS_BY_DIMENSION, UNITS_FLAT = build_all_units()


# =============================================================================
# GENERIC COUNTS / FINANCIAL
# =============================================================================

UNITS_GENERIC: list[str] = [
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
    "packages",
    "containers",
    "loads",
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
    "items",
    "units",
    "basis points",
    "bps",
    "lots",
    "tranches",
]

UNITS: list[str] = UNITS_FLAT + UNITS_GENERIC

_UNIT_PATTERN = build_alternation(UNITS)
QUANTITY_REGEX = re.compile(
    rf"\b({NUMBER_RANGE_STR})\s+(?:{_UNIT_PATTERN})\b", re.IGNORECASE
)


def extract_spans(text: str) -> list[tuple[int, int, str]]:
    if not text:
        return []
    return [
        (m.start(), m.end(), LABELS.QUANTITY.value)
        for m in QUANTITY_REGEX.finditer(text)
    ]
