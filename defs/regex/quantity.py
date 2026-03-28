from __future__ import annotations
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
        "name": "celsius",
        "aliases": [],
        "abbrev": "°C",
        "prefixes": [],
        "extra": [
            "kelvin",
            "degrees celsius",
            "degrees kelvin",
            "centigrade",
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


def mutate_quantity_span(
    text: str,
    *,
    rng: Optional[random.Random] = None,
    strategy: Strategy = "random",
    format_strategy: QuantityFormatStrategy = "random",
    allow_negative: bool = False,
) -> str:
    """
    Mutate the numeric portion of a single quantity span and reinsert it.

    The unit surface form is preserved exactly as extracted.
    """
    if rng is None:
        rng = random.Random()

    values = extract_numeric_values(text)
    if not values:
        return text

    if len(values) == 1:
        mutated_values = [
            mutate_number(
                values[0],
                strategy=strategy,
                int_only=False,
                allow_zero=False,
                allow_negative=allow_negative,
                rng=rng,
            )
        ]
    else:
        mutated_values = mutate_numbers(
            values,
            strategy=strategy,
            int_only=False,
            allow_zero=False,
            allow_negative=allow_negative,
            rng=rng,
        )
        if isinstance(mutated_values, tuple):
            mutated_values = mutated_values[0]
    
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
    return _replace_numeric_cores(text, formatted)


def mutate_quantity_spans(
    spans: Sequence[str],
    *,
    rng: Optional[random.Random] = None,
    strategy: Strategy = "random",
    format_strategy: QuantityFormatStrategy = "random",
    allow_negative: bool = False,
) -> list[str]:
    """
    Mutate a batch of quantity spans.

    A single formatting choice is used for the full batch so related examples
    stay visually coherent.
    """
    if rng is None:
        rng = random.Random()

    values: list[Number] = []
    per_span_counts: list[int] = []
    for span in spans:
        vals = extract_numeric_values(span)
        per_span_counts.append(len(vals))
        values.extend(vals)

    if not values:
        return list(spans)

    mutated_values = mutate_numbers(
        values,
        strategy=strategy,
        int_only=False,
        allow_zero=False,
        allow_negative=allow_negative,
        rng=rng,
    )
    if isinstance(mutated_values, tuple):
        mutated_values = mutated_values[0]

    chosen_format = _normalize_format_strategy(mutated_values[0], format_strategy, rng)

    out: list[str] = []
    idx = 0
    for span, count in zip(spans, per_span_counts):
        if count == 0:
            out.append(span)
            continue
        formatted = [
            format_number(
                v,
                strategy=chosen_format,  # type: ignore[arg-type]
                numeric_only=False,
            )
            for v in mutated_values[idx : idx + count]
        ]
        idx += count
        out.append(_replace_numeric_cores(span, formatted))

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
