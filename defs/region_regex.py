"""Lite replacement for the region matcher that loads pre-exported location data."""

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

DEFAULT_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "region_data.json"


class Region(Enum):
    NORTH_AMERICA = "North America"
    LATIN_AMERICA = "Latin America"
    EUROPE = "Europe"
    MIDDLE_EAST_AFRICA = "Middle East/Africa"
    ASIA_PACIFIC = "Asia/Pacific"
    INTERNATIONAL = "International"


class GeoCode(Enum):
    INTERNATIONAL = "INT"
    NORTH_AMERICA = "NA"
    EUROPE = "EUR"
    ASIA_PACIFIC = "APAC"
    LATIN_AMERICA = "LATAM"
    MIDDLE_EAST_AFRICA = "MEA"


@dataclass
class Location:
    name: str
    phrases: List[str]
    cities: List["Location"] = field(default_factory=list)


@dataclass
class Nation:
    name: str
    phrases: List[str]
    region: Region
    locations: List[Location] = field(default_factory=list)
    code: str = ""


def _load_region_data(path: Optional[Path] = None) -> List[dict]:
    target = Path(path) if path else DEFAULT_DATA_PATH
    if not target.exists():
        raise FileNotFoundError(
            f"{target} is missing. Run scripts/export_region_data.py to regenerate the file."
        )
    with target.open("r", encoding="utf-8") as raw:
        return json.load(raw)


def _build_location(entry: dict) -> Location:
    cities = [Location(name=city.get("name", ""), phrases=city.get("phrases", [])) for city in entry.get("cities", [])]
    return Location(name=entry.get("name", ""), phrases=entry.get("phrases", []), cities=cities)


def _build_nation(entry: dict) -> Nation:
    region_value = entry.get("region")
    try:
        region_enum = Region(region_value)
    except ValueError:
        region_enum = Region.INTERNATIONAL

    locs = [_build_location(loc_entry) for loc_entry in entry.get("locations", [])]

    return Nation(
        name=entry.get("name", ""),
        phrases=entry.get("phrases", []),
        region=region_enum,
        locations=locs,
        code=entry.get("code", ""),
    )


def _group_by_region(raw: List[dict]) -> Dict[Region, List[Nation]]:
    mapping: Dict[Region, List[Nation]] = {region: [] for region in _REGION_ORDER}
    for entry in raw:
        region_value = entry.get("region")
        try:
            region_enum = Region(region_value)
        except ValueError:
            continue
        mapping[region_enum].append(_build_nation(entry))
    for nations in mapping.values():
        nations.sort(key=lambda n: n.name)
    return mapping


_REGION_ORDER = [
    Region.NORTH_AMERICA,
    Region.EUROPE,
    Region.ASIA_PACIFIC,
    Region.LATIN_AMERICA,
    Region.MIDDLE_EAST_AFRICA,
    Region.INTERNATIONAL,
]

_raw_region_data = _load_region_data()
_REGION_MAP = _group_by_region(_raw_region_data)
REGION_SETS: List[List[Nation]] = [_REGION_MAP.get(region, []) for region in _REGION_ORDER]


class RegionMatcher:
    """Minimal RegionMatcher that builds location regexes from exported data."""

    location_map: Dict[str, Tuple[Region, str, Optional[str], str]] = {}
    regex_location_map: Dict[str, Tuple[Region, str, Optional[str], str]] = {}

    location_regexes: List[re.Pattern] = []
    regex_detector_regex = re.compile(r"[\^\$\*\+\?\{\}\[\]\\\|\(\)]")
    _compiled = False

    @classmethod
    def _compile(cls):
        if cls._compiled:
            return

        cls.location_map = {}
        cls.regex_location_map = {}
        cls.location_regexes = []

        def _add_phrase(term: str, info: Tuple[Region, str, Optional[str], str]) -> None:
            if cls.regex_detector_regex.search(term):
                cls.regex_location_map[term] = info
            else:
                cls.location_map[term.lower()] = info

        def _safe_escape(phrases: List[str]) -> List[str]:
            ordered = sorted(phrases, key=len, reverse=True)
            escaped = []
            for phrase in ordered:
                if cls.regex_detector_regex.search(phrase):
                    escaped.append(phrase)
                else:
                    escaped.append(re.escape(phrase))
            return escaped

        for region in REGION_SETS:
            region_phrases = set()
            for nation in region:
                base_info = (nation.region, nation.name, None, nation.code)
                for phrase in nation.phrases + [nation.name]:
                    if phrase:
                        _add_phrase(phrase, base_info)
                        region_phrases.add(phrase)
                for loc in nation.locations:
                    loc_info = (nation.region, nation.name, loc.name, nation.code)
                    if loc.name:
                        _add_phrase(loc.name, loc_info)
                        region_phrases.add(loc.name)
                    for phrase in loc.phrases:
                        _add_phrase(phrase, loc_info)
                        region_phrases.add(phrase)
                    for city in loc.cities:
                        city_info = (nation.region, nation.name, city.name, nation.code)
                        if city.name:
                            _add_phrase(city.name, city_info)
                            region_phrases.add(city.name)
                        for phrase in city.phrases:
                            _add_phrase(phrase, city_info)
                            region_phrases.add(phrase)
            if region_phrases:
                pattern_str = r"\b(?:" + "|".join(_safe_escape(list(region_phrases))) + r")\b"
                cls.location_regexes.append(re.compile(pattern_str, re.IGNORECASE))

        cls._compiled = True

    def __init__(self):
        self._compile()

    @classmethod
    def get_location(
        cls, text: str
    ) -> Optional[Tuple[Region, str, Optional[str], str]]:
        lower = text.lower()
        if lower in cls.location_map:
            return cls.location_map[lower]
        for pattern, info in cls.regex_location_map.items():
            if re.fullmatch(pattern, text, re.IGNORECASE):
                return info
        return None


REGION_CODES = {
    GeoCode.NORTH_AMERICA.value,
    GeoCode.EUROPE.value,
    GeoCode.ASIA_PACIFIC.value,
    GeoCode.LATIN_AMERICA.value,
    GeoCode.MIDDLE_EAST_AFRICA.value,
    GeoCode.INTERNATIONAL.value,
}

TAX_HAVEN_CODES = {
    "KY",
    "BM",
    "VG",
    "CY",
    "MT",
    "JE",
    "GG",
    "IM",
    "LI",
    "MC",
    "BS",
    "BB",
    "CW",
    "MU",
    "PA",
}

MAJOR_CURRENCIES = {
    "USD": {"symbols": ["$"], "names": ["dollar", "dollars"], "prefix": True},
    "EUR": {"symbols": ["€"], "names": ["euro", "euros"], "prefix": True},
    "GBP": {"symbols": ["£"], "names": ["pound", "pounds", "sterling"], "prefix": True},
    "JPY": {"symbols": ["¥"], "names": ["yen"], "prefix": True},
    "CNY": {"symbols": ["¥"], "names": ["yuan", "renminbi"], "prefix": True},
    "INR": {"symbols": ["₹"], "names": ["rupee", "rupees"], "suffix": True},
    "CAD": {"symbols": ["C$", "CAD"], "names": ["canadian dollar"], "prefix": True},
    "AUD": {"symbols": ["A$", "AUD"], "names": ["australian dollar"], "prefix": True},
    "CHF": {"symbols": ["CHF"], "names": ["swiss franc"], "prefix": True},
    "SEK": {"symbols": ["kr"], "names": ["krona", "kronor"], "suffix": True},
    "NOK": {"symbols": ["kr"], "names": ["krone", "kroner"], "suffix": True},
    "DKK": {"symbols": ["kr"], "names": ["krone"], "suffix": True},
    "MXN": {"symbols": ["Mex$"], "names": ["mexican peso"], "prefix": True},
    "BRL": {"symbols": ["R$", "BRL"], "names": ["brazilian real"], "prefix": True},
    "ARS": {"symbols": ["$"], "names": ["peso", "pesos"], "prefix": True},
    "IDR": {"symbols": ["Rp"], "names": ["rupiah"], "prefix": True},
    "KRW": {"symbols": ["₩"], "names": ["won"], "prefix": True},
    "RUB": {"symbols": ["₽"], "names": ["ruble", "rubles", "rouble", "roubles"], "prefix": True},
    "SAR": {"symbols": ["﷼", "SR"], "names": ["riyal", "riyals"], "prefix": True},
    "TRY": {"symbols": ["₺"], "names": ["lira"], "prefix": True},
    "NZD": {"symbols": ["NZ$"], "names": ["new zealand dollar"], "prefix": True},
    "HKD": {"symbols": ["HK$"], "names": ["hong kong dollar"], "prefix": True},
    "SGD": {"symbols": ["S$"], "names": ["singapore dollar"], "prefix": True},
    "AED": {"symbols": ["د.إ", "AED"], "names": ["dirham", "dirhams"], "prefix": True},
    "ILS": {"symbols": ["₪"], "names": ["shekel", "shekels", "new shekel"], "prefix": True},
    "THB": {"symbols": ["฿"], "names": ["baht"], "prefix": True},
    "PLN": {"symbols": ["zł", "zl"], "names": ["zloty", "złoty"], "suffix": True},
    "CZK": {"symbols": ["Kč"], "names": ["koruna", "koruny"], "suffix": True},
    "HUF": {"symbols": ["Ft"], "names": ["forint"], "suffix": True},
    "RON": {"symbols": ["lei"], "names": ["leu", "lei"], "suffix": True},
}
