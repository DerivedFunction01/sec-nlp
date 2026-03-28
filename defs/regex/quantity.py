from __future__ import annotations
import math
import re
import random
from typing import Literal, Optional, Sequence

from defs.labels import LABELS
from defs.regex_lib import build_alternation
from defs.text_cleaner import remap_span, strip_angle_brackets
from defs.number import Number, Strategy, mutate_number, mutate_numbers, format_number


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

SI_PREFIX_FACTORS: dict[str, float] = {
    "kilo": 1_000.0,
    "mega": 1_000_000.0,
    "giga": 1_000_000_000.0,
    "tera": 1_000_000_000_000.0,
    "peta": 1_000_000_000_000_000.0,
    "hecto": 100.0,
    "centi": 0.01,
    "milli": 0.001,
    "micro": 0.000001,
    "nano": 0.000000001,
}

_COMPOUND_FACTORS: dict[str, float] = {
    "hour": 3_600.0,
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
        "prefixes": ["kilo", "hecto", "centi"],
        "factor_to_base": 1.0,
        "derive_area": True,  # generates square metre, km2, etc.
        "derive_volume": True,  # generates cubic metre, m3, etc.
        "suppress_base_abbrev": True,  # bare "m" is too ambiguous in 10-K context
    },
    "mass": {
        "name": "gram",
        "aliases": [],
        "abbrev": "g",
        "prefixes": ["kilo", "mega", "milli"],
        "extra": ["tonne", "tonnes", "metric ton", "metric tons"],
        "factor_to_base": 1.0,
        "suppress_base_abbrev": True,
    },
    "temperature": {
        "name": "centigrade",
        "aliases": [],
        "abbrev": "°C",
        "prefixes": [],
        "extra": [
            "kelvin",
            "degrees celsius",
            "degrees kelvin",
            "celsius",
            "degree centigrade",
        ],
        "factor_to_base": 1.0,
    },
    "volume": {
        "name": "litre",
        "aliases": ["liter"],
        "abbrev": "L",
        "prefixes": ["kilo", "mega", "giga", "milli", "hecto"],
        "factor_to_base": 1.0,
        "suppress_base_abbrev": True,
    },
    "energy": {
        "name": "joule",
        "aliases": [],
        "abbrev": "J",
        "prefixes": ["kilo", "mega", "giga"],
        "factor_to_base": 1.0,
        "suppress_base_abbrev": True,
    },
    "power": {
        "name": "watt",
        "aliases": [],
        "abbrev": "W",
        "prefixes": ["kilo", "mega", "giga"],
        "compounds": [("hour", "h")],  # kilowatt-hour -> kWh
        "factor_to_base": 1.0,
        "suppress_base_abbrev": True,
    },
    "pressure": {
        "name": "pascal",
        "aliases": [],
        "abbrev": "Pa",
        "prefixes": ["kilo", "mega"],
        "factor_to_base": 1.0,
    },
    "electric_current": {
        "name": "ampere",
        "aliases": ["amp"],
        "abbrev": "A",
        "prefixes": ["kilo", "milli"],
        "factor_to_base": 1.0,
        "suppress_base_abbrev": True,
    },
    "voltage": {
        "name": "volt",
        "aliases": [],
        "abbrev": "V",
        "prefixes": ["kilo", "mega", "milli"],
        "factor_to_base": 1.0,
        "suppress_base_abbrev": True,
    },
    "data": {
        "name": "byte",
        "aliases": ["bit"],
        "abbrev": "B",
        "prefixes": ["kilo", "mega", "giga", "tera", "peta"],
        "factor_to_base": 1.0,
        "suppress_base_abbrev": True,
    },
}

# =============================================================================
# IMPERIAL UNITS
# Same dimension keys as SI_UNITS for merging.
# =============================================================================

IMPERIAL_UNITS: dict[str, dict] = {
    "length": {
        "units": [
            {
                "name": "inch",
                "plural": "inches",
                "abbrev": None,
                "factor_to_base": 0.0254,
            },
            {
                "name": "foot",
                "plural": "feet",
                "abbrev": "ft",
                "factor_to_base": 0.3048,
            },
            {
                "name": "yard",
                "plural": "yards",
                "abbrev": "yd",
                "factor_to_base": 0.9144,
            },
            {
                "name": "mile",
                "plural": "miles",
                "abbrev": "mi",
                "factor_to_base": 1609.344,
            },
            {
                "name": "nautical mile",
                "plural": "nautical miles",
                "abbrev": "nm",
                "factor_to_base": 1852.0,
            },
            {
                "name": "furlong",
                "plural": "furlongs",
                "abbrev": None,
                "factor_to_base": 201.168,
            },
            {
                "name": "board foot",
                "plural": "board feet",
                "abbrev": "bf",
                "factor_to_base": 0.002359737216,
            },
            {
                "name": "linear foot",
                "plural": "linear feet",
                "abbrev": "lf",
                "factor_to_base": 0.3048,
            },
        ],
        "derive_area": True,
        "derive_volume": True,
    },
    "mass": {
        "units": [
            {
                "name": "ounce",
                "plural": "ounces",
                "abbrev": "oz",
                "factor_to_base": 28.349523125,
            },
            {
                "name": "pound",
                "plural": "pounds",
                "abbrev": "lb",
                "factor_to_base": 453.59237,
            },
            {
                "name": "ton",
                "plural": "tons",
                "abbrev": None,
                "extra": ["short ton", "short tons", "long ton", "long tons"],
                "factor_to_base": 907184.74,
            },
            {
                "name": "hundredweight",
                "plural": "hundredweights",
                "abbrev": "cwt",
                "factor_to_base": 45359.237,
            },
            {
                "name": "bale",
                "plural": "bales",
                "abbrev": "bl",
                "factor_to_base": 22679.6185,
            },
            {
                "name": "grain",
                "plural": "grains",
                "abbrev": "gr",
                "factor_to_base": 0.06479891,
            },
            {
                "name": "dram",
                "plural": "drams",
                "abbrev": "dr",
                "factor_to_base": 1.7718451953125,
            },
            {
                "name": "slug",
                "plural": "slugs",
                "abbrev": "sl",
                "factor_to_base": 14593.90294,
            },
            # sacks
            {
                "name": "sack",
                "plural": "sacks",
                "abbrev": "sc",
                "factor_to_base": 45359.237,
            },
        ],
    },
    "temperature": {
        "units": [
            {
                "name": "fahrenheit",
                "plural": None,
                "abbrev": "°F",
                "extra": ["degrees fahrenheit"],
                "factor_to_base": 1.0,
            },
        ],
    },
    "volume": {
        "units": [
            {
                "name": "gallon",
                "plural": "gallons",
                "abbrev": "gal",
                "factor_to_base": 3.785411784,
            },
            {
                "name": "quart",
                "plural": "quarts",
                "abbrev": "qt",
                "factor_to_base": 0.946352946,
            },
            {
                "name": "pint",
                "plural": "pints",
                "abbrev": "pt",
                "factor_to_base": 0.473176473,
            },
            {
                "name": "fluid ounce",
                "plural": "fluid ounces",
                "abbrev": "fl oz",
                "factor_to_base": 0.0295735295625,
            },
            {
                "name": "barrel",
                "plural": "barrels",
                "abbrev": "bbl",
                "extra": ["bbl/d"],
                "factor_to_base": 158.987294928,
            },
            {
                "name": "bushel",
                "plural": "bushels",
                "abbrev": None,
                "factor_to_base": 35.23907016688,
            },
            {
                "name": "peck",
                "plural": "pecks",
                "abbrev": None,
                "factor_to_base": 8.80976754172,
            },
            {
                "name": "tablespoon",
                "plural": "tablespoons",
                "abbrev": "tbsp",
                "factor_to_base": 0.01478676478125,
            },
            {
                "name": "teaspoon",
                "plural": "teaspoons",
                "abbrev": "tsp",
                "factor_to_base": 0.00492892159375,
            },
        ],
    },
    "area": {
        "units": [
            {
                "name": "acre",
                "plural": "acres",
                "abbrev": None,
                "factor_to_base": 4046.8564224,
            },
            {
                "name": "hectare",
                "plural": "hectares",
                "abbrev": "ha",
                "factor_to_base": 10000.0,
            },
            {
                "name": "square inch",
                "plural": "square inches",
                "abbrev": "in2",
                "extra": ["sq in"],
                "factor_to_base": 0.00064516,
            },
        ],
    },
    "energy": {
        "units": [
            {
                "name": "btu",
                "plural": None,
                "abbrev": None,
                "extra": ["mmbtu", "mmbtu/h"],
                "factor_to_base": 1055.05585262,
            },
            {
                "name": "therm",
                "plural": "therms",
                "abbrev": None,
                "factor_to_base": 105_505_585.262,
            },
            {
                "name": "dekatherm",
                "plural": "dekatherms",
                "abbrev": "dth",
                "factor_to_base": 1_055_055_852.62,
            },
            # foot pound
            {
                "name": "foot[- ]pound",
                "plural": "foot[- ]pounds",
                "abbrev": "fp",
                "factor_to_base": 1.3558179483314,
            },
        ],
    },
    "power": {
        "units": [
            {
                "name": "horsepower",
                "plural": None,
                "abbrev": "hp",
                "factor_to_base": 745.6998715822702,
            },
        ],
    },
    "gas_volume": {
        "units": [
            {
                "name": "mcf",
                "plural": None,
                "abbrev": None,
                "factor_to_base": 28.316846592,
            },
            {
                "name": "mmcf",
                "plural": None,
                "abbrev": None,
                "factor_to_base": 28_316.846592,
            },
            {
                "name": "bcf",
                "plural": None,
                "abbrev": None,
                "factor_to_base": 28_316_846.592,
            },
            {
                "name": "standard cubic foot",
                "plural": "standard cubic feet",
                "abbrev": "scf",
                "factor_to_base": 0.028316846592,
            },
            {
                "name": "gpm",
                "plural": None,
                "abbrev": None,
                "factor_to_base": 0.003785411784,
            },
            # stb
            {
                "name": "stock tank barrel",
                "plural": "stock tank barrels",
                "abbrev": "stb",
                "factor_to_base": 158.987294928,
            },
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
        forms = [n, f"{n}s"]
        for form in forms:
            terms += [f"square {form}", f"sq {form}"]
        if abbrev:
            terms += [f"sq {abbrev}", f"{abbrev}2"]
    return terms


def _derive_volume_terms(
    name: str, aliases: list[str], abbrev: str | None
) -> list[str]:
    terms: list[str] = []
    for n in [name] + aliases:
        forms = [n, f"{n}s"]
        for form in forms:
            terms += [f"cubic {form}", f"cu {form}"]
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
    if abbrev and not config.get("suppress_base_abbrev"):
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


UNITS: list[str] = UNITS_FLAT
UNITS_COMPACT: list[str] = [
    term.replace(" ", "")
    for term in UNITS_FLAT
    if " " in term or len(term) <= 3 or any(ch.isdigit() for ch in term)
]

_UNIT_PATTERN = build_alternation(UNITS)
_COMPACT_UNIT_PATTERN = build_alternation(UNITS_COMPACT)
_QUANTITY_NUMBER_CORE_STR = r"(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+)"
_QUANTITY_RANGE_SEP_STR = build_alternation(
    [
        r"-",
        r"–",
        r"—",
        r"to",
        r"and",
        r"(?:out\s+)?of(?:\s+[A-Za-z][\w'-]*){0,5}",
        r"through",
    ]
)
_QUANTITY_NUMBER_RANGE_STR = rf"{_QUANTITY_NUMBER_CORE_STR}(?:\s*{_QUANTITY_RANGE_SEP_STR}\s*{_QUANTITY_NUMBER_CORE_STR})?"
QUANTITY_RE = re.compile(
    rf"(?<!\d,)\b({_QUANTITY_NUMBER_RANGE_STR})\s+(?:{_UNIT_PATTERN})\b",
    re.IGNORECASE,
)
QUANTITY_COMPACT_RE = re.compile(
    rf"(?<!\d,)\b({_QUANTITY_NUMBER_RANGE_STR})(?:{_COMPACT_UNIT_PATTERN})\b",
    re.IGNORECASE,
)

_QUANTITY_NUMERIC_CORE_RE = re.compile(r"(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+)")
_QUANTITY_PREFIX_RE = re.compile(rf"^(?P<num>{_QUANTITY_NUMBER_RANGE_STR})")


def _sanitize_unit_surface(term: str, unit_terms_lower: set[str]) -> str:
    """
    Normalize regex-oriented unit terms into readable display text.

    This keeps the mutator from emitting raw regex fragments like
    ``foot[- ]pound`` while staying within extractable surface forms.
    """
    surface = term.replace("[- ]", "-")
    if surface.endswith("ss") and surface[:-1].lower() in unit_terms_lower:
        surface = surface[:-1]
    return surface


def _is_compact_surface(surface: str) -> bool:
    return " " not in surface


def _lookup_unit_entry(surface: str) -> dict[str, object] | None:
    """
    Find a unit entry using a few forgiving surface variants.

    This helps normalize space vs hyphen spellings for regex-y terms like
    ``foot[- ]pound``.
    """
    candidates = [
        surface,
        surface.replace(" ", "-"),
        surface.replace("-", " "),
    ]
    for candidate in candidates:
        entry = UNIT_CATALOG_BY_SURFACE.get(candidate.lower())
        if entry is not None:
            return entry
    return None


def _build_quantity_unit_catalog() -> dict[str, list[dict[str, object]]]:
    """
    Build per-dimension unit candidates with factors to the base unit.

    The result is used by the mutator to swap units within the same dimension.
    """
    raw_terms_lower = {t.lower() for t in UNITS_FLAT}
    catalog: dict[str, list[dict[str, object]]] = {}

    def add_term(dimension: str, term: str, factor: float) -> None:
        surface = _sanitize_unit_surface(term, raw_terms_lower)
        entry = {
            "surface": surface,
            "factor_to_base": factor,
            "dimension": dimension,
            "compact": _is_compact_surface(surface),
        }
        catalog.setdefault(dimension, []).append(entry)

    for dimension, config in SI_UNITS.items():
        base_factor = float(config.get("factor_to_base", 1.0))
        name = config["name"]
        aliases = config.get("aliases", [])
        abbrev = config.get("abbrev", "")
        prefixes = config.get("prefixes", [])
        compounds = config.get("compounds", [])
        extra = config.get("extra", [])

        for n in [name] + aliases:
            add_term(dimension, n, base_factor)
            add_term(dimension, f"{n}s", base_factor)
        if abbrev and not config.get("suppress_base_abbrev"):
            add_term(dimension, abbrev, base_factor)

        for prefix in prefixes:
            prefix_factor = SI_PREFIX_FACTORS.get(prefix, 1.0)
            for n in [name] + aliases:
                add_term(dimension, f"{prefix}{n}", base_factor * prefix_factor)
                add_term(dimension, f"{prefix}{n}s", base_factor * prefix_factor)
            if abbrev:
                add_term(dimension, f"{SI_PREFIXES.get(prefix, '')}{abbrev}", base_factor * prefix_factor)
                for compound_name, compound_abbrev in compounds:
                    compound_factor = _COMPOUND_FACTORS.get(compound_name, 1.0)
                    add_term(dimension, f"{prefix}{name}-{compound_name}", base_factor * prefix_factor * compound_factor)
                    add_term(dimension, f"{prefix}{name} {compound_name}", base_factor * prefix_factor * compound_factor)
                    if compound_abbrev:
                        add_term(
                            dimension,
                            f"{SI_PREFIXES.get(prefix, '')}{abbrev}{compound_abbrev}",
                            base_factor * prefix_factor * compound_factor,
                        )

        if config.get("derive_area"):
            for n in [name] + aliases:
                add_term("area", f"square {n}", base_factor**2)
                add_term("area", f"square {n}s", base_factor**2)
                add_term("area", f"sq {n}", base_factor**2)
                add_term("area", f"sq {n}s", base_factor**2)
            if abbrev:
                add_term("area", f"sq {abbrev}", base_factor**2)
                add_term("area", f"{abbrev}2", base_factor**2)
            for prefix in prefixes:
                prefix_factor = SI_PREFIX_FACTORS.get(prefix, 1.0)
                pref_factor = (base_factor * prefix_factor) ** 2
                prefixed_name = f"{prefix}{name}"
                add_term("area", f"square {prefixed_name}", pref_factor)
                add_term("area", f"square {prefixed_name}s", pref_factor)
                add_term("area", f"sq {prefixed_name}", pref_factor)
                add_term("area", f"sq {prefixed_name}s", pref_factor)
                if abbrev:
                    add_term("area", f"{SI_PREFIXES.get(prefix, '')}{abbrev}2", pref_factor)

        if config.get("derive_volume"):
            for n in [name] + aliases:
                add_term("volume", f"cubic {n}", base_factor**3)
                add_term("volume", f"cubic {n}s", base_factor**3)
                add_term("volume", f"cu {n}", base_factor**3)
                add_term("volume", f"cu {n}s", base_factor**3)
            if abbrev:
                add_term("volume", f"cu {abbrev}", base_factor**3)
                add_term("volume", f"{abbrev}3", base_factor**3)
            for prefix in prefixes:
                prefix_factor = SI_PREFIX_FACTORS.get(prefix, 1.0)
                pref_factor = (base_factor * prefix_factor) ** 3
                prefixed_name = f"{prefix}{name}"
                add_term("volume", f"cubic {prefixed_name}", pref_factor)
                add_term("volume", f"cubic {prefixed_name}s", pref_factor)
                add_term("volume", f"cu {prefixed_name}", pref_factor)
                add_term("volume", f"cu {prefixed_name}s", pref_factor)
                if abbrev:
                    add_term("volume", f"{SI_PREFIXES.get(prefix, '')}{abbrev}3", pref_factor)

        for term in extra:
            add_term(dimension, term, base_factor)

    for dimension, config in IMPERIAL_UNITS.items():
        for unit in config.get("units", []):
            unit_factor = float(unit["factor_to_base"])
            name = unit["name"]
            plural = unit.get("plural")
            abbrev = unit.get("abbrev")
            extra = unit.get("extra", [])

            add_term(dimension, name, unit_factor)
            if plural:
                add_term(dimension, plural, unit_factor)
            if abbrev:
                add_term(dimension, abbrev, unit_factor)
            for term in extra:
                add_term(dimension, term, unit_factor)

            if config.get("derive_area"):
                add_term("area", f"square {name}", unit_factor**2)
                add_term("area", f"sq {name}", unit_factor**2)
                if plural:
                    add_term("area", f"square {plural}", unit_factor**2)
                    add_term("area", f"sq {plural}", unit_factor**2)
                if abbrev:
                    add_term("area", f"sq {abbrev}", unit_factor**2)
                    add_term("area", f"{abbrev}2", unit_factor**2)
            if config.get("derive_volume"):
                add_term("volume", f"cubic {name}", unit_factor**3)
                add_term("volume", f"cu {name}", unit_factor**3)
                if plural:
                    add_term("volume", f"cubic {plural}", unit_factor**3)
                    add_term("volume", f"cu {plural}", unit_factor**3)
                if abbrev:
                    add_term("volume", f"cu {abbrev}", unit_factor**3)
                    add_term("volume", f"{abbrev}3", unit_factor**3)

    deduped: dict[str, list[dict[str, object]]] = {}
    for dimension, entries in catalog.items():
        seen: set[str] = set()
        out: list[dict[str, object]] = []
        for entry in entries:
            key = str(entry["surface"]).lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(entry)
        deduped[dimension] = out
    return deduped


UNIT_CATALOG_BY_DIMENSION = _build_quantity_unit_catalog()
UNIT_CATALOG_BY_SURFACE: dict[str, dict[str, object]] = {}
for dimension, entries in UNIT_CATALOG_BY_DIMENSION.items():
    for entry in entries:
        UNIT_CATALOG_BY_SURFACE[str(entry["surface"]).lower()] = entry

QuantityFormatStrategy = Literal[
    "random",
    "raw",
    "commas",
    "magnitude_long",
    "magnitude_short",
    "magnitude_financial",
]

_QUANTITY_FORMATS_SMALL = ("raw", "commas")
_QUANTITY_FORMATS_MEDIUM = ("commas", "magnitude_long")
_QUANTITY_FORMATS_LARGE = ("commas", "magnitude_long", "magnitude_short", "magnitude_financial")


def extract_numeric_values(text: str) -> list[Number]:
    """
    Extract numeric values from a quantity span or fragment.

    Only the leading numeric prefix is considered so unit suffixes like `m2`
    are not mistaken for extra values.
    """
    if not text:
        return []

    m = _QUANTITY_PREFIX_RE.match(text)
    if not m:
        return []

    values: list[Number] = []
    for num_match in _QUANTITY_NUMERIC_CORE_RE.finditer(m.group("num")):
        raw = num_match.group("num")
        cleaned = raw.replace(",", "")
        try:
            value = float(cleaned)
        except ValueError:
            continue
        values.append(int(value) if value.is_integer() else value)
    return values


def _replace_numeric_cores(text: str, replacements: Sequence[str]) -> str:
    prefix_match = _QUANTITY_PREFIX_RE.match(text)
    if not prefix_match:
        return text

    prefix = prefix_match.group("num")
    suffix = text[prefix_match.end("num") :]
    it = iter(replacements)

    def repl(match: re.Match[str]) -> str:
        try:
            return next(it)
        except StopIteration:
            return match.group(0)

    replaced_prefix = _QUANTITY_NUMERIC_CORE_RE.sub(repl, prefix)
    return replaced_prefix + suffix


def _pick_quantity_format(value: Number, rng: random.Random) -> str:
    magnitude = abs(float(value))
    if magnitude < 1_000:
        return rng.choice(_QUANTITY_FORMATS_SMALL)
    if magnitude < 100_000:
        return rng.choice(_QUANTITY_FORMATS_MEDIUM)
    return rng.choice(_QUANTITY_FORMATS_LARGE)


def _normalize_format_strategy(
    value: Number,
    format_strategy: QuantityFormatStrategy,
    rng: random.Random,
) -> str:
    if format_strategy != "random":
        return format_strategy
    return _pick_quantity_format(value, rng)


def _round_quantity_value(value: Number) -> Number:
    """
    Round quantity values to a human-friendly precision.

    Unit conversion can introduce long floating tails, but quantity spans do
    not need that level of exactness in this pipeline.
    """
    rounded = round(float(value), 3)
    if math.isclose(rounded, round(rounded)):
        return int(round(rounded))
    return rounded


def _split_quantity_surface(text: str) -> tuple[str, str, str] | None:
    """
    Split a quantity span into (numeric_prefix, separator, unit_surface).

    The separator preserves the original whitespace between the number and unit.
    """
    prefix_match = _QUANTITY_PREFIX_RE.match(text)
    if not prefix_match:
        return None

    numeric_prefix = prefix_match.group("num")
    rest = text[prefix_match.end("num") :]
    separator = rest[: len(rest) - len(rest.lstrip())]
    unit_surface = rest.lstrip()
    return numeric_prefix, separator, unit_surface


def _pick_quantity_unit(
    current_surface: str,
    rng: random.Random,
    reference_value: Number | None = None,
) -> tuple[str, float] | None:
    """
    Pick a replacement unit from the same dimension as `current_surface`.

    Tries to preserve the compact/spaced style of the source unit when possible.
    """
    current_entry = _lookup_unit_entry(current_surface)
    if not current_entry:
        return None

    dimension = str(current_entry["dimension"])
    current_compact = bool(current_entry["compact"])
    candidates = [
        entry
        for entry in UNIT_CATALOG_BY_DIMENSION.get(dimension, [])
        if str(entry["surface"]).lower() != current_surface.lower()
    ]
    if not candidates:
        return current_surface, float(current_entry["factor_to_base"])

    same_style = [entry for entry in candidates if bool(entry["compact"]) == current_compact]
    pool = same_style or candidates
    if reference_value is not None:
        source_factor = float(current_entry["factor_to_base"])
        ref_abs = abs(float(reference_value))
        scored: list[tuple[float, dict[str, object]]] = []
        for entry in pool:
            target_factor = float(entry["factor_to_base"])
            converted = ref_abs * source_factor / target_factor if target_factor else ref_abs
            if 0.1 <= converted < 10_000:
                score = 0.0
            elif converted <= 0:
                score = 1_000.0
            else:
                score = abs(math.log10(converted))
            scored.append((score, entry))
        best_score = min(score for score, _ in scored)
        best_pool = [entry for score, entry in scored if score == best_score]
        chosen = rng.choice(best_pool)
    else:
        chosen = rng.choice(pool)
    return str(chosen["surface"]), float(chosen["factor_to_base"])


def mutate_quantity_span(
    text: str,
    *,
    rng: Optional[random.Random] = None,
    strategy: Strategy = "random",
    format_strategy: QuantityFormatStrategy = "random",
    mutate_unit: bool = True,
    allow_negative: bool = False,
) -> str:
    """
    Mutate the numeric portion of a single quantity span and reinsert it.

    By default the unit is also converted to another unit in the same
    dimension using factor_to_base.
    """
    if rng is None:
        rng = random.Random()

    values = extract_numeric_values(text)
    if not values:
        return text

    split = _split_quantity_surface(text)
    if split is None:
        return text

    numeric_prefix, separator, unit_surface = split
    unit_surface = unit_surface.strip()

    target_surface = unit_surface
    source_factor = 1.0
    target_factor = 1.0
    if mutate_unit:
        picked = _pick_quantity_unit(unit_surface, rng, reference_value=values[0])
        if picked is not None:
            target_surface, target_factor = picked
            source_entry = _lookup_unit_entry(unit_surface)
            if source_entry is not None:
                source_factor = float(source_entry["factor_to_base"])

    if len(values) == 1:
        transformed_values = [values[0]]
        if mutate_unit and source_factor != target_factor:
            transformed_values = [float(values[0]) * source_factor / target_factor]
        mutated_values = [
            mutate_number(
                transformed_values[0],
                strategy=strategy,
                int_only=False,
                allow_zero=False,
                allow_negative=allow_negative,
                rng=rng,
            )
        ]
    else:
        transformed_values = values
        if mutate_unit and source_factor != target_factor:
            transformed_values = [float(v) * source_factor / target_factor for v in values]
        mutated_values = mutate_numbers(
            transformed_values,
            strategy=strategy,
            int_only=False,
            allow_zero=False,
            allow_negative=allow_negative,
            rng=rng,
        )
        if isinstance(mutated_values, tuple):
            mutated_values = mutated_values[0]

    mutated_values = [_round_quantity_value(v) for v in mutated_values]

    assert isinstance(mutated_values[0], Number)
    chosen_format = _normalize_format_strategy(mutated_values[0], format_strategy, rng)
    formatted = [
        format_number(
            v,
            strategy=chosen_format,  # type: ignore[arg-type]
            numeric_only=False,
        )
        for v in mutated_values
        if isinstance(v, Number)
    ]
    numeric_text = _replace_numeric_cores(numeric_prefix, formatted)
    return f"{numeric_text}{separator}{target_surface}"


def mutate_quantity_spans(
    spans: Sequence[str],
    *,
    rng: Optional[random.Random] = None,
    strategy: Strategy = "random",
    format_strategy: QuantityFormatStrategy = "random",
    mutate_unit: bool = True,
    allow_negative: bool = False,
) -> list[str]:
    """
    Mutate a batch of quantity spans.

    A single formatting choice is used for the full batch so related examples
    stay visually coherent.
    """
    if rng is None:
        rng = random.Random()

    out: list[str] = []
    for span in spans:
        # Each span mutates independently, but all stay within the same
        # precision rules used by `mutate_quantity_span`.
        out.append(
            mutate_quantity_span(
                span,
                rng=rng,
                strategy=strategy,
                format_strategy=format_strategy,
                mutate_unit=mutate_unit,
                allow_negative=allow_negative,
            )
        )

    return out


def extract_spans(text: str) -> list[tuple[str, int, int, str]]:
    if not text:
        return []

    stripped, pos_map = strip_angle_brackets(text)
    results = []

    for m in QUANTITY_RE.finditer(stripped):
        orig_start, orig_end = remap_span(pos_map, m.start(), m.end())
        results.append(
            (text[orig_start:orig_end], orig_start, orig_end, LABELS.QUANTITY.value)
        )

    for m in QUANTITY_COMPACT_RE.finditer(stripped):
        orig_start, orig_end = remap_span(pos_map, m.start(), m.end())
        candidate = (text[orig_start:orig_end], orig_start, orig_end, LABELS.QUANTITY.value)
        if not any(not (orig_end <= s or orig_start >= e) for _, s, e, _ in results):
            results.append(candidate)

    return results
