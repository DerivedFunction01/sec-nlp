from __future__ import annotations
import re
from typing import Optional
from defs.regex.shares import _EQUITY_CONTEXT_RE
from defs.regex_lib import NUMBER_PATTERN_STR, NUMBER_RANGE_STR, SENTENCE_SPLIT_RE, add_restrictions, build_alternation, build_compound
from defs.labels import LABELS
from defs.regex.labor import GENERIC_WORKER_TERMS, WORKER_TERMS

# Unambiguously ENTITY_COUNT
ORGANIZATIONAL_TERMS = {
    r"compan(?:y|ies)",
    r"corporations?",
    r"subsidiar(?:y|ies)",
    r"affiliates?",
    r"airlines?",
    r"airplanes?",
    r"helicopters?",
    r"jets?",
    # not to ship, but ship/vessel
    add_restrictions(r"ships?",lookbehinds=[r"to"]),
    r"vessels?",
    r"freights?",
    r"unions",
    r"partnerships?",
    r"ventures?",
    r"competitors?",
    r"suppliers?",
    r"customers?",
    r"clients?",
    r"contractors?",
    r"dealers?",
    r"distributors?",
    r"agenc(?:y|ies)",
    r"programs?",
}

PRODUCT_TERMS = {
    r"products?",
    r"brands?",
    r"lines?",  # product lines
    r"models?",
    r"patents?",
    r"licenses?",
    r"contracts?",
    r"agreements?",
    r"permits?",
    r"instruments?",
    r"polic(?:y|ies)",
    r"trusts?",
    r"grants?",
}


def build_energy_dynamic_pattern() -> str:
    prefixes = [
        "bio",
        "liquefied",
        "liquid",
    ]

    bases = [
        "fuels?",
        "oils?",
        "energy",
        "coal",
        "gas(?:oline)?",
        "propane",
        "petroleum",
        "diesel",
        "butane",
        "electricity",
        "distillates",
        "ethane",
        "ethanol",
        "kerosene",
        "LNG",
        "LPG",
        "solar",
        "wind",
    ]

    modifiers = [
        "bunker",
        "marine",
        "jet",
        "(?:air|aero)plane",
        "helicopter",
        "plane",
        "aero",
        "aviation",
        "crude",
        "heating",
        "coking",
        "natural",
        "carbon",
        "renewable",
        "liquid",
    ]

    prefix_alt = build_alternation(prefixes, sort_longest_first=True)
    modifier_alt = build_alternation(modifiers, sort_longest_first=True)
    base_alt = build_alternation(bases, sort_longest_first=True)

    # Optional prefix, optional modifier, required base, optional second base
    return (
        rf"(?:(?:{prefix_alt})[- ])?"
        rf"(?:(?:{modifier_alt})[- ])?"
        rf"(?:{base_alt})"
        rf"(?:[- ](?:{base_alt}|liquids?|power))?"
    )


def build_metals_dynamic_pattern() -> str:
    """
    Dynamically build comprehensive Metals patterns.
    Allows:
        prefix? modifier? base (base)?
    """

    prefixes = [
        "precious",
        "rare earth",
        "base",
        "scrap",
        "silicon",
    ]

    # Optional: add more if you want "raw copper", "refined nickel", etc.
    modifiers = [
        "stainless",
        "refined",
        "raw",
        "unrefined",
        "high[- ]grade",
        "low[- ]grade",
    ]

    bases = [
        "aluminum",
        "copper",
        "iron",
        "gold",
        "silver",
        "metals?",
        "ores?",
        "(?:stainless[- ])?steel",
        "titanium",
        "uranium",
        "nickel",
        "zinc",
        "lead",
        "tin",
        "platinum",
        "palladium",
        "rhodium",
        "cobalt",
        "molybdenum",
        "chromium",
        "lithium",
        "magnesium",
        "vanadium",
        "alumina",
        "bauxite",
        "antimony",
        "arsenic",
        "bismuth",
        "indium",
        "gallium",
        "graphite",
        "potassium",
        "diamonds?",
        "gemstones?",
    ]

    prefix_alt = build_alternation(prefixes, sort_longest_first=True)
    modifier_alt = build_alternation(modifiers, sort_longest_first=True)
    base_alt = build_alternation(bases, sort_longest_first=True)

    # prefix? modifier? base base?
    return (
        rf"(?:(?:{prefix_alt})[- ])?"
        rf"(?:(?:{modifier_alt})[- ])?"
        rf"(?:{base_alt})"
        rf"(?:[- ](?:{base_alt}))?"
    )


COMMODITY_MAP = {
    "crops": [
        # --- Fruits ---
        "oranges?",
        "bananas?",
        "apples?",
        "grapes?",
        "avocados?",
        "mango(?:es)?",
        "pineapples?",
        "papayas?",
        "fruits?",
        "kiwi(?:s)?",
        "lemon(?:s)?",
        "lime(?:s)?",
        "peach(?:es)?",
        "pear(?:s)?",
        "plum(?:s)?",
        "apricot(?:s)?",
        "fig(?:s)?",
        "olive(?:s)?",
        "coconut(?:s)?",
        # --- Berries ---
        "strawberr(?:y|ies)",
        "blueberr(?:y|ies)",
        "raspberr(?:y|ies)",
        "cherr(?:y|ies)",
        "berr(?:y|ies)",
        "cranberr(?:y|ies)",
        # --- Vegetables ---
        "tomato(?:es)?",
        "potato(?:es)?",
        "garlic",
        "pumpkins?",
        "peppers?",
        "peas?",
        "carrots?",
        "onions?",
        "cabbages?",
        "lettuces?",
        "spinach",
        "broccoli",
        "cauliflowers?",
        "vegetables?",
        "cucumber(?:s)?",
        "eggplant(?:s)?",
        "zucchini",
        "squash(?:es)?",
        "sweet potato(?:es)?",
        "turnip(?:s)?",
        "radish(?:es)?",
        "asparagus",
        "celer(?:y|ies)",
        # --- Grains / Cereals ---
        "corns?",
        "grains?",
        "wheats?",
        "rices?",
        "barley",
        "oats?",
        "rye",
        "sorghum",
        "millet",
        "quinoa",
        "buckwheats?",
        "triticale",
        "cereals?",
        "oatmeals?",
        # --- Oilseeds ---
        "soybeans?",
        "canola",
        "sunflowers?",
        "palm oils?",
        "rapeseeds?",
        "flax",
        "hemp",
        "soy",
        # --- Legumes / Pulses ---
        "lentils?",
        "chickpeas?",
        "beans?",
        "peas?",
        "legumes?",
        "pulses?",
        # --- Nuts ---
        "almonds?",
        "walnuts?",
        "pecans?",
        "pistachios?",
        # --- Roots / Tubers ---
        "cassava",
        "yams?",
        "beets?",
        # --- Fungi ---
        "mushrooms?",
        # --- Specialty Crops ---
        "cocoa",
        "coffee",
        "cotton",
        "sugars?",
        "tea",
        "tobacco",
        # --- General Crop Categories ---
        "(?:horticultural|row) crops?",
        # -- Other ---
        "honey",
        "beeswax",
        "spices?",
        "(?:(?:bell|spicy|sweet|green|red|chili|jalape[nñ]o|banana|ghost|cayenne)[- ])?peppers?",
        # Certain peppers
        "jalape[nñ]os?",
        "california reapers?",
        "paprika",
        "cinnamon",
        "cloves?",
        "nutmeg",
        "ginger",
        "turmeric",
        "vanilla",
        "saffron",
        "essential oils?",  # borderline but traded physically
        "(?:natural[- ])?rubber",
        "latex",
        "gum arabic",
        "seeds?",
    ],
    "livestock": [
        "dairy",
        "milk",
        "livestocks?",
        "eggs?",
        "cattle",
        "chickens?",
        "pork",
        "turkeys?",
        "avian",
        "hogs?",
        "lean hogs?",
        "(?:feeder|live) cattle",
        "poultry",
        "beef",
        "meat",
        "lamb",
        "wool",
        "sheep",
        "goats?",
        "mutton",
        "veal",
        "bisons?",
        "buffalos?",
        "ducks?",
        "geese?",
        "broilers?",
        "swines?",
        "sows?",
        "boars?",
        "calves?",
        "heifers?",
        "ruminants?",
        "livestock feeds?",
        "feedlots?",
        "feedstocks?",
        "turkeys?",
        "ducks?",
        "goose",
        "geese",
        "waterfowls?",
        "guinea fowls?",
        "rabbits?",
        "venisons?",
        "alpacas?",
        "llamas?",
        "yaks?",
        "butter",
        "cheeses?",
        "whey",
        "milk powders?",
        "dry milk",
        "dry whey",
    ],
    "seafood": [
        "salmon",
        "fish(?:es)?",
        "shrimps?",
        "crabs?",
        "lobsters?",
        "tunas?",
        "seafoods?",
        "aquaculture",
        "prawns?",
        "scallops?",
        "oysters?",
        "clams?",
        "mussels?",
        "squids?",
        "octop(?:i|us)",
        "halibuts?",
        "cods?",
        "haddocks?",
        "tilapias?",
        "snappers?",
        "mackerels?",
        "anchov(?:i|es)",
        "sardines?",
        "trouts?",
        "catfish",
        "(?:king|snow|blue) crabs?",
        "shellfish(?:es)?",
        "bivalves?",
        "crustaceans?",
        "sea bass",
        "bass",
        "yellowtail",
        "albacore",
        "eels?",
        "uni",
        "roe",
        "caviars?",
        "seaweeds?",
        "kelps?",
        "mariculture",
        "pollocks?",
        "hake",
        "herring",
        "plaice",
        "flounders?",
        "groupers?",
        "mahi-mahi",
        "swordfish",
        "kingfish",
        "pomfret",
        "abalone",
        "sea urchin",
        "periwinkle",
        "sharks?",
        "whales?",
        "dolphins?",
    ],
    "energy": [
        "biodiesel",
        "biomass",
        build_energy_dynamic_pattern(),
        "condensate",
        "naphtha",
    ],
    "chemicals": [
        "fertilizer",
        "nitrogen",
        "petrochemical",
        "phosphate",
        "plastic",
        "polymer",
        "potash",
        "resin",
        "rubber",
        "soda ash",
        "sulfur",
        "salt",
        "silicon",
        "urea",
        "ammonia",
        "carbon",
    ],
    "metals": [build_metals_dynamic_pattern()],
    "construction": [
        "asphalt",
        "bitumen",
        "cement",
        "concrete",
        "gravel",
        "limestone",
        "sand",
        "clay",
        "slate",
        "granite",
        "marble",
        "gypsum",
        "plaster",
        "mortar",
        "bricks?",
        "ballast",
        "dolomite",
        "basalt",
        "quartzite",
        "pavers?",
        "tiles?",
        "drywall",
        "sheetrock",
        "insulation",
        "fiberglass",
        "roofing materials?",
        "shingles?",
        "precast panels?",
    ],
    "forestry": [
        "(?:hardwood|softwood) lumber",
        "logs?",
        "lumber",
        "(?:ply|hard|soft|sawn)woods?",
        "timber",
        "woods?",
        "wood (?:chips?|pellets?|fibers?|panels?|pulps?)",
        r"(?<!commercial[ -])papers?",
        r"cardboards?",
        r"cartons?",
        "pulps?",
        # --- Added ---
        "veneers?",
        "kraft papers?",
    ],
    "general": [
        "raw materials?",
        "textiles?",
        "commodit(?:y|ies)",
    ],
}

COMMON_COMMODITIES = [item for sublist in COMMODITY_MAP.values() for item in sublist]

# Derivatives
FINANCIAL_INSTRUMENTS = {
    "core": {
        r"swaps?",
        r"collars?",
        r"forward",
        r"hedges?",
        r"hedging",
        r"caps?",
        r"locks?",
        r"floors?",
        r"futures",
        r"options?",
        r"spreads?",
        r"derivatives?",
        r"financial",
        r"index",
        r"loans?",
        r"bonds?",
        r"notes?",
        r"mortgages?",
        r"(?:credit|debt|loan|revolving|term|senior)\s+facilit(?:y|ies)",
        r"puts?",
        r"calls?",
    },
    "ending": {
        r"contracts?",
        r"options?",
        r"agreements?",
        r"arrangements?",
        r"assets?",
        r"liabiliy(?:y|ies)",
        r"derivatives?",
        r"instruments?",
        r"swaptions?",
    },
    "prefix": {
        r"interest",
        r"treasury",
        r"forward",
        r"fixed",
        r"floating",
        r"variable",
        r"pay",
        r"receive",
        r"rate",
        r"price",
        r"commodity",
        r"currency",
        r"foreign",
        r"exchange",
        r"equity",
        r"cryptocurrency",
        r"trading",
        r"starting",
        r"libor",
        r"sonia",
        r"embedded",
        r"back[-\s]to[-\s]back",
        r"open",
        r"linked",
        r"cross",
        r"credit",
        r"default",
        r"debt",
        r"term",
        r"revolving",
        r"senior",
        r"secured",
        r"barrier",
        r"exotic",
        r"american",
        r"european",
        r"asian",
        r"bermudan",
        r"vanilla",
        r"binary",
        r"bitcoin",
        r"ethereum",
        r"calendar",
        r"quanto",
        r"otc",
        r"over[-\s]the[-\s]counter",
        r"overnight",
    },
}
_FI_PREFIX_PATTERN = build_alternation(list(FINANCIAL_INSTRUMENTS["prefix"]) + COMMON_COMMODITIES)
_FI_CORE_PATTERN = build_alternation(list(FINANCIAL_INSTRUMENTS["core"]))
_FI_ENDING_PATTERN = build_alternation(list(FINANCIAL_INSTRUMENTS["ending"]))

# Any word that belongs to the FI vocabulary (prefix | core), repeated 0-6 times
# Free words (non-digit) allowed anywhere in the modifier chain
_FI_FREE_GAP = r"(?:[A-Za-z][\w]*[-\s]+){0,3}"

_FI_MODIFIER_GAP = (
    rf"(?:(?:{_FI_PREFIX_PATTERN}|{_FI_CORE_PATTERN}|{_FI_FREE_GAP})[-\s]+){{0,6}}"
)

# Must end with a core OR ending term
_FI_TERMINAL = rf"(?:{_FI_CORE_PATTERN}|{_FI_ENDING_PATTERN})"

FINANCIAL_INSTRUMENT_COUNT_RE = re.compile(
    rf"\b({NUMBER_RANGE_STR})\s+({_FI_MODIFIER_GAP}{_FI_TERMINAL})\b",
    re.IGNORECASE,
)

# --- Ambiguous: context decides ---
AMBIGUOUS_TERMS = {
    r"segments?",  
    r"divisions?", 
    r"markets?",
    r"groups?", 
    r"networks?",  
    r"channels?",  
    r"portfolios?",
    r'types?',
}

GENERIC_COUNT_NOUNS = {
    r"pieces?",
    r"parts?",
    r"components?",
    r"elements?",
    r"slots?",
    r"seats?",
    r"positions?",
    r"spaces?",
    r"trips?",
    r"visits?",
    r"calls?",
    r"transactions?",
    r"orders?",
    r"shipments?",
    r"deliver(?:y|ies)",
    r"packages?",
    r"containers?",
    r"loads?",
    r"sheets?",
    r"coils?",
    r"bundles?",
    r"pallets?",
    r"sacks?",
    r"bales?",
    r"heads?",
    r"carats?",
    r"ingots?",
    r"bars?",
    r"items?",
    r"units?",
    r"basis\s+points?",
    r"bps",
    r"lots?",
    r"tranches?",
    r"confirmations?",
    r"purchases",
}

_ENTITY_TERMS = list(ORGANIZATIONAL_TERMS | PRODUCT_TERMS | AMBIGUOUS_TERMS | GENERIC_COUNT_NOUNS)
_ENTITY_TERM_PATTERN = build_alternation(_ENTITY_TERMS)
_GENERIC_WORKER_PATTERN = build_alternation(list(GENERIC_WORKER_TERMS))

_ENTITY_FILLER = build_alternation(
    [
        r"independent",
        r"international",
        r"national",
        r"dependent",
        r"domestic",
        r"foreign",
        r"global",
        r"regional",
        r"local",
        r"regional",
        r"affiliate",
        r"strategic",
        r"major",
        r"minor",
        r"different",
        r"similar",
        r"several",
        r"third[-\s]party",
        r"trade",
        r"labo(?:u)r",
        r"union",
        r"(?:collective\s+)?bargaining",
    ] + COMMON_COMMODITIES
)
_ENTITY_FILLER_GAP = rf"(?:{_ENTITY_FILLER}\s*(?:and|or|,)?\s*){{0,4}}"
_ENTITY_GAP = r"(?:[^\W\d][\w\.-]*\s+){0,1}"
ENTITY_COUNT_RE = re.compile(
    rf"\b({NUMBER_PATTERN_STR})\s+({_ENTITY_FILLER_GAP}{_ENTITY_GAP}"
    rf"(?:{_ENTITY_TERM_PATTERN}))"
    rf"(?!\s+(?:{_GENERIC_WORKER_PATTERN})\b)\b",
    re.IGNORECASE,
)

# Standalone counts like "5 CBAs"
_STANDALONE_TERMS = [
    r"cba(?:s)?",
    r"nda(?:s)?",
    r"mou(?:s)?",
    r"(?:collective\s+)?bargaining\s+units",
]

_STANDALONE_PATTERN = build_alternation(_STANDALONE_TERMS)
ENTITY_STANDALONE_RE = re.compile(
    rf"\b({NUMBER_PATTERN_STR})\s+({_STANDALONE_PATTERN})\b",
    re.IGNORECASE,
)

# Bargaining units (treat as ENTITY_COUNT, not labor)
_BU_WORKER_PATTERN = build_alternation(list(WORKER_TERMS))
_BU_WORKER_PHRASE = r"(?:[^\W\d][\w-]{3,}\s+){0,1}" rf"(?:{_BU_WORKER_PATTERN})(?:['’]s?)?"
BARGAINING_UNIT_COUNT_RE = re.compile(
    rf"\b({NUMBER_PATTERN_STR})\s+((?:{_BU_WORKER_PHRASE}\s+)?"
    rf"(?:collective\s+)?bargaining\s+units?)\b",
    re.IGNORECASE,
)

from defs.text_cleaner import strip_angle_brackets, remap_span
from defs.regex_lib import build_regex

# Terms where a preceding year-like number is likely a year, especially if singular
_YEAR_PRONE_TERMS = [
    r"programs?",
    r"contracts?",
    r"agreements?",
    r"permits?",
    r"licenses?",
    r"ventures?",
    r"partnerships?",
    r"plans?",
    r"polic(?:y|ies)",
    r"trusts?",
    r"grants?",
]
_YEAR_PRONE_RE = build_regex(_YEAR_PRONE_TERMS)

# Terms that could be either SHARE or ENTITY
_AMBIGUOUS_SHARE_ENTITY_TERMS = {
    r"options?",
    r"warrants?",
    r"rights?",
    r"awards?",
    r"grants?",
    r"units?", # e.g. RSUs, PSUs
}
_AMBIGUOUS_SHARE_ENTITY_RE = build_regex(_AMBIGUOUS_SHARE_ENTITY_TERMS)

_IMMEDIATE_COUNT_VERBS = [
    r"have", r"had", r"has", r"having", r"are", r"is", r"were", r"was"
]
_IMMEDIATE_COUNT_VERB_RE = re.compile(
    rf"\b(?:{'|'.join(_IMMEDIATE_COUNT_VERBS)})\s+$",
    re.IGNORECASE
)

def _iter_sentences(src: str) -> list[tuple[int, int, str]]:
    out: list[tuple[int, int, str]] = []
    start = 0
    for m in SENTENCE_SPLIT_RE.finditer(src):
        end = m.end()
        chunk = src[start:end]
        if chunk.strip():
            out.append((start, end, chunk))
        start = end
    tail = src[start:]
    if tail.strip():
        out.append((start, len(src), tail))
    return out

def _number_value(num_text: str) -> int:
    first = re.split(r"[-–—]|\bto\b", num_text, maxsplit=1)[0]
    try:
        return int(float(first.replace(",", "")))
    except (ValueError, IndexError):
        return 0

def extract_spans(text: str) -> list[tuple[str, int, int, str]]:
    """
    Extract ENTITY_COUNT spans from text using entity-specific rules.
    Returns (start, end, label) tuples.
    """
    if not text:
        return []

    stripped, pos_map = strip_angle_brackets(text)
    spans: list[tuple[str, int, int, str]] = []
    span_set: set[tuple[str, int, int, str]] = set()
    stripped_spans: list[tuple[int, int]] = []

    def _add_span(start: int, end: int, num_val: Optional[int] = None, label: str = LABELS.ENTITY_COUNT.value) -> None:
        orig_start, orig_end = remap_span(pos_map, start, end)
        item = (text[orig_start:orig_end], orig_start, orig_end, label)
        if item in span_set:
            return
        span_set.add(item)
        spans.append(item)
        stripped_spans.append((start, end))

    def _overlaps_existing(start: int, end: int) -> bool:
        for s, e in stripped_spans:
            if not (end <= s or start >= e):
                return True
        return False

    def _is_year_like(num_str: str, entity_text: str, pre_context: str, is_fi: bool = False) -> bool:
        if _IMMEDIATE_COUNT_VERB_RE.search(pre_context):
            return False
            
        try:
            num_val_str = num_str.replace(',', '').split('-')[0]
            num_val = int(float(num_val_str))
            if 1970 <= num_val <= 2050:
                # Treat as a year if it's a financial instrument or a year-prone term, 
                # regardless of whether it's plural (e.g., "2024 swaps", "2025 contracts")
                if is_fi or _YEAR_PRONE_RE.search(entity_text):
                    return True
        except (ValueError, IndexError):
            pass
        return False

    for sent_start, _, sentence in _iter_sentences(stripped):
        has_equity_context = bool(_EQUITY_CONTEXT_RE.search(sentence))

        for pat in [FINANCIAL_INSTRUMENT_COUNT_RE, ENTITY_COUNT_RE, ENTITY_STANDALONE_RE, BARGAINING_UNIT_COUNT_RE]:
            is_fi = pat is FINANCIAL_INSTRUMENT_COUNT_RE
            for m in pat.finditer(sentence):
                num_str = m.group(1)
                entity_text = m.group(2)

                # 1. Check for year-like numbers
                if _is_year_like(num_str, entity_text, sentence[:m.start()], is_fi):
                    continue

                # 2. Check for share/entity ambiguity
                if has_equity_context and _AMBIGUOUS_SHARE_ENTITY_RE.search(entity_text):
                    continue # Let shares.py handle it

                # 3. Add span if it doesn't overlap
                if not _overlaps_existing(sent_start + m.start(), sent_start + m.end()):
                    _add_span(sent_start + m.start(), sent_start + m.end())

    return spans
