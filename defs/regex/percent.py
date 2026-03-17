import re

from defs.regex_lib import to_build_alternation, build_regex
from defs.labels import LABELS

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
    r"(?:in)?effective",
    r"nominal",
    r"weighted",
    r"annual(?:ized)?",
    r"daily",
    r"weekly",
    r"monthly",
    r"quarterly",
    r"yearly",
    r"average",
    r"applicable",
    r"stated",
    r"blended",
    r"total",
    r"overall",
    r"combined",
    r"global",
    r"consolidated",
    r"aggregated",
    r"net",
    r"gross",
]

PCT_RATE_CORE = [
    r"interest",
    r"discount",
    r"exchange",
    r"tax",
    r"dividend",
    r"inflation",
    r"deflation",
    r"yield",
    r"coupon",
    r"spread",
    r"margin",
    r"return",
    r"cap",
    r"capped",
    r"floor",
    r"collar",
    r"market",
    r"currency",
    r"treasury",
    r"variable",
    r"floating",
    r"forward",
    r"fixed",
    r"unionization",
    r"coverage",
    r"default",
    r"credit",
    r"swap",
]

PCT_RATE_SUFFIX = [
    r"rates?(?:\s+(?:cap|floor|collar))?",
    r"ratios?",
    r"yields?",
]

_MOD_PAT = rf"(?:{to_build_alternation(PCT_RATE_MODIFIERS)})"
_CORE_PAT = rf"(?:{to_build_alternation(PCT_RATE_CORE)})"
_SUFFIX_PAT = rf"(?:{to_build_alternation(PCT_RATE_SUFFIX)})"

# Structure: [MOD*] CORE+ SUFFIX
# One or more core terms, must end with a suffix
PCT_RATE_RE = re.compile(
    rf"\b(?:{_MOD_PAT}\s+)*"  # zero or more modifiers
    rf"(?:{_CORE_PAT}\s+)*"  # zero or more core terms
    rf"{_SUFFIX_PAT}\b",  # required suffix
    re.IGNORECASE,
)

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
    r"[A-Z][a-z]+(?:ese|ish|an|ch)?",  # nationality/proper adj: Japanese, American
]

_DET = rf"(?:{to_build_alternation(PCT_OF_DETERMINERS)})\s+"
_MOD = rf"(?:[A-Za-z][\w-]*(?:'s|s')?\s+)"

_PCT_OF_CHAIN = (
    rf"{_DET}{{1,4}}"  # 1-3 determiners: "of the", "of each of the"
    rf"{_MOD}{{0,3}}"  # up to 3 modifier words
)

PCT_OF_PATTERN = re.compile(
    rf"\b(\d+(?:\.\d+)?(?:%|{to_build_alternation(PCT)})\s+{_PCT_OF_CHAIN}([A-Za-z][\w-]+))\b",
    re.IGNORECASE,
)

# Change terms are simpler — no compound structure needed
PCT_CHANGE_RE = build_regex(PCT_CHANGE_TERMS)


def extract_spans(text: str) -> list[tuple[int, int, str]]:
    """
    Extract PERCENT spans from text.
    Returns (start, end, label) tuples.
    """
    if not text:
        return []

    spans: list[tuple[int, int, str]] = []

    def _closest_distance(start: int, end: int, matches: list[re.Match]) -> int | None:
        if not matches:
            return None
        best = None
        for m in matches:
            if m.end() <= start:
                dist = start - m.end()
            elif m.start() >= end:
                dist = m.start() - end
            else:
                dist = 0
            if best is None or dist < best:
                best = dist
        return best

    def _label_for_span(start: int, end: int) -> str:
        # Find nearest change/rate term and label based on distance
        max_distance = 200
        change_matches = list(PCT_CHANGE_RE.finditer(text))
        rate_matches = list(PCT_RATE_RE.finditer(text))

        change_dist = _closest_distance(start, end, change_matches)
        rate_dist = _closest_distance(start, end, rate_matches)

        if change_dist is not None and change_dist <= max_distance:
            return LABELS.PCT_CHANGE.value
        if rate_dist is not None and rate_dist <= max_distance:
            return LABELS.PCT_RATE.value
        return LABELS.PCT_OTHER.value

    for m in PCT_RANGE.finditer(text):
        spans.append((m.start(), m.end(), _label_for_span(m.start(), m.end())))

    for m in PCT_OF_PATTERN.finditer(text):
        spans.append((m.start(1), m.end(1), _label_for_span(m.start(1), m.end(1))))

    for m in PCT_REGEX.finditer(text):
        spans.append((m.start(), m.end(), _label_for_span(m.start(), m.end())))

    return spans
