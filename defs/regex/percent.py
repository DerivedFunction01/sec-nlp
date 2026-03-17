import re

from defs.regex_lib import to_build_alternation, build_regex

PCT_CHANGE_TERMS = [
    r"increas(?:es?|ed|ing)",
    r"decreas(?:es?|ed|ing)",
    r"declin(?:es?|ed|ing|ation)",
    r"reduc(?:es?|ed|ing|tion)",
    r"grow(?:ing|th)|grew",
    r"gain(?:ed|ing|s)?",
    r"loss(?:es?)?|los(?:e|ing)",
    r"chang(?:es?|ed|ing)",
    r"ris(?:e|ing)|rose",
    r"fall(?:ing)|fell",
    r"drop(?:ped|ping)",
    r"jump(?:ed|ing)",
    r"surg(?:es?|ed|ing)",
    r"improve(?:d|s|ment)?",
    r"deteriorat(?:es?|ed|ing|ion)",
    "uptick",
    "downtick",
]

PCT_RATE_MODIFIERS = [
    "(?:in)?effective",
    "nominal",
    "weighted",
    "weighted",
    "annual(?:ized)?",
    "daily",
    "weekly",
    "monthly",
    "quarterly",
    "yearly",
    "average",
    "applicable",
    "stated",
    "blended",
]

PCT_RATE_CORE = [
    "interest",
    "discount",
    "exchange",
    "tax",
    "dividend",
    "inflation",
    "deflation",
    "yield",
    "coupon",
    "spread",
    "margin",
    "return",
    "forward",
    "fixed",
    "cap",
    "capped",
    "floor",
    "collar",
    "market",
    "currency",
    "treasury",
    "variable",
    "floating",
    "unionization",
    "coverage"
]

PCT_RATE_SUFFIX = [
    "rates?",
    "ratios?",
    "yields?",
    "floor",
    "cap",
    "share",
    "collar",
]

PCT = [
    r"per[- ]cent(?:age)?(?:\s+(?:rates?|points?))?",
]

PCT_REGEX = build_regex(PCT)
PCT_SPACE = re.compile(r"(\d)\s+%", re.IGNORECASE)
PCT_RANGE = re.compile(
    rf"\b(\d+(?:\.\d+)?)\s*%?\s*(?:-|–|—|to)\s*(\d+(?:\.\d+)?)\s*(?:%|{to_build_alternation(PCT)})",
    re.IGNORECASE,
)

PCT_OF_DETERMINERS = [
    r"the",
    r"a",
    r"an",
    r"each",
    r"all",
    r"any",
    r"our",
    r"its",
    r"their",
    r"his",
    r"her",
]

PCT_OF_POSSESSIVES = [
    r"company(?:'s)?",
    r"registrant(?:'s)?",
    r"subsidiar(?:y|ies)(?:'s)?",
    r"corporation(?:'s)?",
    r"consolidated",
    r"[\w]+(?:'s|s')",  # any possessive noun
]

PCT_OF_MODIFIERS = [
    r"total",
    r"overall",
    r"combined",
    r"global",
    r"consolidated",
    r"aggregated?",
    r"net",
    r"gross",
    r"remaining",
    r"outstanding",
    r"issued",
    r"voting",
    r"common",
    r"19\d{2}|20\d{2}",  # year as modifier
    r"[A-Z][a-z]+(?:ese|ish|an|ch)?",  # nationality/proper adj: Japanese, American
]

_DET = rf"(?:{to_build_alternation(PCT_OF_DETERMINERS)})\s+"
_POSS = rf"(?:{to_build_alternation(PCT_OF_POSSESSIVES)})"
_MOD = rf"(?:[A-Za-z][\w-]*(?:'s|s')?\s+)"

_PCT_OF_CHAIN = (
    rf"{_DET}{{1,3}}"  # 1-3 determiners: "of the", "of each of the"
    rf"(?:{_POSS}\s+)?"  # optional possessive
    rf"{_MOD}{{0,3}}"  # up to 3 modifier words
)

PCT_OF_PATTERN = re.compile(
    rf"\b(\d+(?:\.\d+)?(?:%|{to_build_alternation(PCT)})\s+{_PCT_OF_CHAIN}([A-Za-z][\w-]+)\b",
    re.IGNORECASE,
)


PCT_RATE_TERMS = PCT_RATE_MODIFIERS + PCT_RATE_CORE + PCT_RATE_SUFFIX
alt = to_build_alternation(PCT_RATE_TERMS)
PCT_TEXT_PAT = rf"(?:{alt})(?:[\s-]+(?:{alt}))*"

# Change terms are simpler — no compound structure needed
PCT_CHANGE_RE = build_regex(PCT_CHANGE_TERMS)
