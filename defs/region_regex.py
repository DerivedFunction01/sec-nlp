from __future__ import annotations
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


def _build_bare_currency_default_map() -> dict[str, str]:
    """
    Map bare currency names to a default code.

    This is intentionally conservative: it only includes single-token names
    (so it skips forms like "south african rand"), and it keeps the first code
    encountered in MAJOR_CURRENCIES for shared names like "peso" and "krona".
    """
    defaults: dict[str, str] = {}
    for code, props in MAJOR_CURRENCIES.items():
        for name in props.get("names", []):
            if not name:
                continue
            bare = name.strip().lower()
            if " " in bare:
                continue
            defaults.setdefault(bare, code)
    return defaults


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

NATION_BY_CODE: dict[str, Nation] = {}
for region in REGION_SETS:
    for nation in region:
        if nation.code:
            NATION_BY_CODE[nation.code.upper()] = nation


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
    "USD": {
        "symbols": ["$"],
        "names": ["dollar", "dollars", "US dollar", "US dollars"],
        "prefix": True,
        "adj": "american",
    },
    "EUR": {
        "symbols": ["€"],
        "names": ["euro", "euros"],
        "prefix": True,
        "adj": "european",
    },
    "GBP": {
        "symbols": ["£"],
        "names": ["pound", "pounds", "sterling"],
        "prefix": True,
        "amb_names": ["pound", "pounds"],
        "adj": "british",
    },
    "JPY": {
        "symbols": ["¥"],
        "names": ["yen", "japanese yuan"],
        "prefix": True,
        "adj": "japanese",
    },
    "CNY": {
        "symbols": ["¥"],
        "names": ["yuan", "renminbi", "chinese yuan"],
        "prefix": True,
        "adj": "chinese",
    },
    "INR": {
        "symbols": ["₹"],
        "names": ["rupee", "rupees", "indian rupee", "indian rupees"],
        "suffix": True,
        "adj": "indian",
    },
    "CAD": {
        "symbols": ["C$", "CAD"],
        "names": ["canadian dollar"],
        "prefix": True,
        "adj": "canadian",
    },
    "AUD": {
        "symbols": ["A$", "AUD"],
        "names": ["australian dollar"],
        "prefix": True,
        "adj": "australian",
    },
    "CHF": {
        "symbols": ["CHF"],
        "names": ["swiss franc"],
        "prefix": True,
        "adj": "swiss",
    },
    "SEK": {
        "symbols": ["kr"],
        "amb_symbols": ["kr"],
        "names": ["krona", "kronor", "swedish krona", "swedish kronor"],
        "suffix": True,
        "adj": "swedish",
    },
    "NOK": {
        "symbols": ["kr"],
        "amb_symbols": ["kr"],
        "names": ["krone", "kroner", "norwegian krone", "norwegian kroner"],
        "suffix": True,
        "adj": "norwegian",
    },
    "DKK": {
        "symbols": ["kr"],
        "amb_symbols": ["kr"],
        "names": ["danish krone", "danish kroner"],
        "suffix": True,
        "adj": "danish",
    },
    "MXN": {
        "symbols": ["Mex$"],
        "names": ["mexican peso", "mexican pesos", "pesos", "peso"],
        "prefix": True,
        "adj": "mexican",
    },
    "BRL": {
        "symbols": ["R$", "BRL"],
        "names": ["brazilian real"],
        "prefix": True,
        "adj": "brazilian",
    },
    "ARS": {
        "symbols": ["$"],
        "names": ["peso", "pesos", "argentine peso", "argentine pesos"],
        "prefix": True,
        "adj": "argentine",
    },
    "IDR": {
        "symbols": ["Rp"],
        "names": ["rupiah"],
        "prefix": True,
        "adj": "indonesian",
    },
    "KRW": {
        "symbols": ["₩"],
        "names": ["won"],
        "prefix": True,
        "amb_names": ["won"],
        "adj": "korean",
    },
    "RUB": {
        "symbols": ["₽"],
        "names": ["ruble", "rubles", "rouble", "roubles"],
        "prefix": True,
        "adj": "russian",
    },
    "SAR": {
        "symbols": ["﷼", "SR"],
        "names": ["riyal", "riyals"],
        "prefix": True,
        "adj": "saudi",
    },
    "TRY": {
        "symbols": ["₺"],
        "names": ["lira"],
        "prefix": True,
        "adj": "turkish",
    },
    "BHD": {
        "symbols": ["BHD"],
        "names": ["bahraini dinar", "bahraini dinars", "dinar", "dinars"],
        "amb_names": ["dinar", "dinars"],
        "prefix": True,
        "adj": "bahraini",
    },
    "BWP": {
        "symbols": ["BWP"],
        "names": ["botswanan pula", "pula"],
        "prefix": True,
        "adj": "botswanan",
    },
    "BND": {
        "symbols": ["B$", "BND"],
        "names": ["brunei dollar"],
        "prefix": True,
        "adj": "bruneian",
    },
    "BGN": {
        "symbols": ["BGN", "лв"],
        "names": ["bulgarian lev", "lev"],
        "suffix": True,
        "adj": "bulgarian",
    },
    "NZD": {
        "symbols": ["NZ$"],
        "names": ["new zealand dollar"],
        "prefix": True,
        "adj": "new zealand",
    },
    "HKD": {
        "symbols": ["HK$"],
        "names": ["hong kong dollar"],
        "prefix": True,
        "adj": "hong kong",
    },
    "SGD": {
        "symbols": ["S$"],
        "names": ["singapore dollar"],
        "prefix": True,
        "adj": "singaporean",
    },
    "AED": {
        "symbols": ["د.إ", "AED"],
        "names": ["dirham", "dirhams"],
        "prefix": True,
        "adj": "emirati",
    },
    "ILS": {
        "symbols": ["₪"],
        "names": [
            "shekel",
            "shekels",
            "new shekel",
            "sheqel",
            "sheqels",
            "new sheqel",
            "new shekels",
            "new sheqels",
        ],
        "prefix": True,
        "adj": "israeli",
    },
    "THB": {"symbols": ["฿"], "names": ["baht"], "prefix": True, "adj": "thai"},
    "PLN": {
        "symbols": ["zł", "zl"],
        "names": ["zloty", "złoty"],
        "suffix": True,
        "adj": "polish",
    },
    "CZK": {
        "symbols": ["Kč"],
        "names": ["koruna", "koruny"],
        "suffix": True,
        "adj": "czech",
    },
    "HRK": {
        "symbols": ["HRK"],
        "names": ["croatian kuna", "kuna"],
        "suffix": True,
        "adj": "croatian",
    },
    "HUF": {
        "exact_symbols": ["Ft"],
        "names": ["forint"],
        "suffix": True,
        "adj": "hungarian",
    },
    "ISK": {
        "symbols": ["ISK"],
        "names": ["icelandic krona", "krona"],
        "suffix": True,
        "amb_names": ["krona"],
        "adj": "icelandic",
    },
    "IRR": {
        "symbols": ["IRR"],
        "names": ["iranian rial", "iranian rials", "rials", "rial"],
        "prefix": True,
        "adj": "iranian",
    },
    "KZT": {
        "symbols": ["₸", "KZT"],
        "names": ["kazakhstani tenge", "tenge"],
        "prefix": True,
        "adj": "kazakhstani",
    },
    "KWD": {
        "symbols": ["KWD", "د.ك"],
        "names": ["kuwaiti dinar", "kuwaiti dinars", "dinar", "dinars"],
        "prefix": True,
        "adj": "kuwaiti",
    },
    "MUR": {
        "symbols": ["MUR"],
        "names": ["mauritian rupee", "mauritian rupees", "rupee", "rupees"],
        "amb_names": ["rupee", "rupees"],
        "suffix": True,
        "adj": "mauritian",
    },
    "RON": {
        "symbols": ["lei"],
        "names": ["leu", "lei"],
        "suffix": True,
        "adj": "romanian",
    },
    # South Africa
    "ZAR": {
        "exact_symbols": ["R"],
        "names": ["rand", "south african rand"],
        "prefix": True,
        "amb_names": ["rand"],
        "adj": "south african",
    },
    "TWD": {
        "symbols": ["NT$"],
        "names": ["new taiwan dollar", "taiwan dollar"],
        "prefix": True,
        "adj": "taiwanese",
    },
    "PHP": {
        "symbols": ["₱"],
        "names": ["philippine peso", "philippine pesos", "peso", "pesos"],
        "amb_names": ["peso", "pesos"],
        "prefix": True,
        "adj": "philippine",
    },
    "MYR": {
        "symbols": ["RM"],
        "names": ["ringgit", "malaysian ringgit"],
        "prefix": True,
        "adj": "malaysian",
    },
    "NPR": {
        "symbols": ["NPR"],
        "names": ["nepalese rupee", "nepalese rupees"],
        "amb_names": ["rupee", "rupees"],
        "suffix": True,
        "adj": "nepalese",
    },
    "COP": {
        "symbols": ["COL$"],
        "names": ["colombian peso", "colombian pesos", "peso", "pesos"],
        "amb_names": ["peso", "pesos"],
        "prefix": True,
        "adj": "colombian",
    },
    "CLP": {
        "symbols": ["CLP$"],
        "names": ["chilean peso", "chilean pesos", "peso", "pesos"],
        "amb_names": ["peso", "pesos"],
        "prefix": True,
        "adj": "chilean",
    },
    "PEN": {
        "symbols": ["S/", "S/."],
        "amb_symbols": ["S/", "S/."],
        "names": ["sol", "peruvian sol"],
        "prefix": True,
        "amb_names": ["sol"],
        "adj": "peruvian",
    },
    "EGP": {
        "symbols": ["E£"],
        "names": ["egyptian pound", "egyptian pounds"],
        "prefix": True,
        "adj": "egyptian",
    },
    "NGN": {
        "symbols": ["₦"],
        "names": ["naira", "nigerian naira"],
        "prefix": True,
        "adj": "nigerian",
    },
    "PKR": {
        "symbols": ["₨"],
        "names": ["pakistani rupee", "pakistani rupees", "rupee", "rupees"],
        "amb_names": ["rupee", "rupees"],
        "prefix": True,
        "adj": "pakistani",
    },
    "OMR": {
        "symbols": ["OMR", "ر.ع."],
        "names": ["omani rial", "omani rials", "rial", "rials"],
        "amb_names": ["rial", "rials"],
        "prefix": True,
        "adj": "omani",
    },
    "QAR": {
        "symbols": ["QAR", "ر.ق."],
        "names": ["qatari rial", "qatari rials", "rial", "rials"],
        "amb_names": ["rial", "rials"],
        "prefix": True,
        "adj": "qatari",
    },
    "VND": {
        "symbols": ["₫"],
        "names": ["dong", "vietnamese dong"],
        "prefix": True,
        "adj": "vietnamese",
    },
    "LKR": {
        "symbols": ["LKR"],
        "names": ["sri lankan rupee", "sri lankan rupees", "rupee", "rupees"],
        "amb_names": ["rupee", "rupees"],
        "suffix": True,
        "adj": "sri lankan",
    },
    "TTD": {
        "symbols": ["TT$", "TTD"],
        "names": ["trinidad dollar", "trinidad and tobago dollar"],
        "prefix": True,
        "adj": "trinidad",
    },
    "UAH": {
        "symbols": ["₴", "UAH"],
        "names": ["ukrainian hryvnia", "hryvnia", "hryvnias"],
        "prefix": True,
        "adj": "ukrainian",
    },
    "VES": {
        "symbols": ["VES"],
        "names": ["venezuelan bolivar", "bolivar", "bolivars"],
        "prefix": True,
        "adj": "venezuelan",
    },
    "ZWL": {
        "symbols": ["ZWL"],
        "names": ["zimbabwean dollar"],
        "prefix": True,
        "adj": "zimbabwean",
    },
}

# Bare currency name -> default code.
# This is used for shared bare forms like "peso" / "pesos" and for common
# one-word names like "yen" or "dollar" when no country context is present.
BARE_CURRENCY_NAME_TO_DEFAULT_CODE: dict[str, str] = _build_bare_currency_default_map()

# Nation code -> compatible currency codes.
# This is intentionally separate from MAJOR_CURRENCIES so the matcher can use
# it as routing metadata without conflating nation codes with currency codes.
NATION_TO_CURRENCY_CODES: dict[str, set[str]] = {
    "US": {"USD"},
    "CA": {"CAD"},
    "MX": {"MXN"},
    "BR": {"BRL"},
    "AR": {"ARS"},
    "CL": {"CLP"},
    "CO": {"COP"},
    "PE": {"PEN"},
    "GB": {"GBP"},
    "JP": {"JPY"},
    "CN": {"CNY"},
    "IN": {"INR"},
    "AU": {"AUD"},
    "NZ": {"NZD"},
    "HK": {"HKD"},
    "SG": {"SGD"},
    "TH": {"THB"},
    "TW": {"TWD"},
    "ID": {"IDR"},
    "KR": {"KRW"},
    "MY": {"MYR"},
    "PH": {"PHP"},
    "VN": {"VND"},
    "SA": {"SAR"},
    "AE": {"AED"},
    "IL": {"ILS"},
    "TR": {"TRY"},
    "BH": {"BHD"},
    "BW": {"BWP"},
    "BN": {"BND"},
    "BG": {"BGN"},
    "EG": {"EGP"},
    "NG": {"NGN"},
    "PK": {"PKR"},
    "CH": {"CHF"},
    "HR": {"HRK"},
    "IS": {"ISK"},
    "IR": {"IRR"},
    "KZ": {"KZT"},
    "KW": {"KWD"},
    "MU": {"MUR"},
    "NP": {"NPR"},
    "OM": {"OMR"},
    "QA": {"QAR"},
    "LK": {"LKR"},
    "TT": {"TTD"},
    "SE": {"SEK"},
    "NO": {"NOK"},
    "DK": {"DKK"},
    "PL": {"PLN"},
    "CZ": {"CZK"},
    "HU": {"HUF"},
    "RO": {"RON"},
    "RU": {"RUB"},
    "ZA": {"ZAR"},
    "UA": {"UAH"},
    "VE": {"VES"},
    "ZW": {"ZWL"},
    "EU": {"EUR"},
    "DE": {"EUR"},
    "FR": {"EUR"},
    "IT": {"EUR"},
    "ES": {"EUR"},
    "PT": {"EUR"},
    "NL": {"EUR"},
    "BE": {"EUR"},
    "AT": {"EUR"},
    "FI": {"EUR"},
    "IE": {"EUR"},
    "GR": {"EUR"},
    "SI": {"EUR"},
    "SK": {"EUR"},
    "LV": {"EUR"},
    "LT": {"EUR"},
    "EE": {"EUR"},
    "LU": {"EUR"},
    "CY": {"EUR"},
    "MT": {"EUR"},
}


def _unique_preserve_order(items: List[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _is_plain_surface(term: str) -> bool:
    return not bool(re.search(r"[\^\$\*\+\?\{\}\[\]\\\|\(\)]", term))


def _titlecase_surface(term: str) -> str:
    parts = re.split(r"(\s+|-)", term)
    titled: List[str] = []
    for part in parts:
        if part == "" or part.isspace() or part == "-":
            titled.append(part)
            continue
        if part.isupper():
            titled.append(part)
        elif part.lower() in {"us", "usa"}:
            titled.append(part.upper())
        else:
            titled.append(part[:1].upper() + part[1:].lower())
    return "".join(titled)


def get_compatible_currency_codes(nation_code: str) -> set[str]:
    """
    Return the currency codes associated with a nation code.

    The mapping is intentionally permissive for shared-currency regions like
    the euro area.
    """
    return set(NATION_TO_CURRENCY_CODES.get(nation_code.upper(), set()))
