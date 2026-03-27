from __future__ import annotations
import re
from defs.regex_lib import build_alternation
from defs.labels import LABELS


# =============================================================================
# ADDRESS TERMS
# =============================================================================

STREET_TERMS: list[str] = [
    # Existing
    r"ave(?:nue)?\.?",
    r"street",
    r"st\.?",
    r"blvd\.?",
    r"boulevard",
    r"cir(?:cle)?\.?",
    r"court",
    r"ct\.?",
    r"road",
    r"rd\.?",
    r"lane",
    r"ln\.?",
    r"drive",
    r"dr\.?",
    r"highway",
    r"hwy\.?",
    r"route",
    r"rt\.?",
    # Places / Ways
    r"place",
    r"pl\.?",
    r"way",
    r"wy\.?",
    # Terrace / Trail
    r"terrace",
    r"ter(?:r)?\.?",
    r"trail",
    r"trl\.?",
    # Parkway / Expressway / Freeway / Turnpike
    r"parkway",
    r"pkwy\.?",
    r"expressway",
    r"expy\.?",
    r"freeway",
    r"fwy\.?",
    r"turnpike",
    r"tpke?\.?",
    # Pike / Pass / Path / Walk / Loop / Alley / Run / Bend / Trace
    r"pike",
    r"pass",
    r"path",
    r"walk",
    r"loop",
    r"alley",
    r"aly\.?",
    r"run",
    r"bend",
    r"trace",
    # Broadway and similar named-street suffixes
    r"broadway",
    # Additional common suffixes
    r"square",
    r"sq\.?",
    r"plaza",
    r"plz\.?",
    r"crossing",
    r"xing\.?",
    r"junction",
    r"jct\.?",
    r"center",
    r"ctr\.?",
]
UNIT_TERMS: list[str] = [
    r"floors?",
    r"apts?",
    r"apartments?",
    r"suites?",
    r"units?",
    r"rooms?",
    r"buildings?",
    r"bldgs?",
    r"p\.?o\.?\s*box",
]

ADDRESS_COMPONENT_TERMS: list[str] = [
    r"box",
    r"routes?",
    r"highways?",
    r"interstate",
]

# =============================================================================
# COMPILED PATTERNS
# =============================================================================

ZIP_CODE_RE = re.compile(r"\b\d{5}(?:[- ]\d{4})?\b")

_street_terms = build_alternation(STREET_TERMS)
_unit_terms = build_alternation(UNIT_TERMS)
_address_terms = build_alternation(ADDRESS_COMPONENT_TERMS)

STREET_ADDRESS_RE = re.compile(
    rf"\b\d{{1,6}}[A-Za-z]{{0,2}}\s+[A-Za-z0-9][\w\s\-']{{1,40}}\s+(?:{_street_terms})\b",
    re.IGNORECASE,
)

UNIT_RE = re.compile(
    rf"\b(?:{_unit_terms})\s+(?:#\.?\s*|no\.?\s*)?\d+[A-Za-z]?\b",
    re.IGNORECASE,
)

ADDRESS_COMPONENT_RE = re.compile(
    rf"\b(?:{_address_terms})\s+(?:#\.?\s*|no\.?\s*)?\d+[A-Za-z]?\b",
    re.IGNORECASE,
)

# =============================================================================
# PHONE PATTERNS
# =============================================================================

_SEP = r"[-.\s]"
_OPT_SEP = r"[-.\s]?"
_EXT = r"(?:\s*(?:x|ext\.?)\s*\d{1,5})?"

_PHONE_FORMATS: dict[str, tuple] = {
    "US_CA": (
        r"1",
        rf"(?:\(?\d{{3}}\)?{_OPT_SEP})\d{{3}}{_SEP}\d{{4}}",
    ),
    "UK": (
        r"44",
        rf"(?:\(?0?\d{{2,4}}\)?{_OPT_SEP})\d{{3,4}}{_SEP}\d{{3,4}}",
    ),
    "FR": (
        r"33",
        rf"0?\d{_OPT_SEP}\d{{2}}{_SEP}\d{{2}}{_SEP}\d{{2}}{_SEP}\d{{2}}",
    ),
    "DE": (
        r"49",
        rf"\d{{2,5}}{_SEP}\d{{3,8}}",
        True,  # requires_country_code
    ),
    "IT": (
        r"39",
        rf"0?\d{{1,4}}{_SEP}\d{{4,8}}",
    ),
    "JP": (
        r"81",
        rf"0?\d{{1,4}}{_SEP}\d{{4}}{_SEP}\d{{4}}",
    ),
    "CN": (
        r"86",
        rf"(?:1\d{{2}}{_SEP}\d{{4}}{_SEP}\d{{4}}|0\d{{2,3}}{_SEP}\d{{4}}{_SEP}\d{{4}})",
    ),
    "IN": (
        r"91",
        rf"\d{{5}}{_SEP}\d{{5}}",
    ),
    "BR": (
        r"55",
        rf"(?:\(?\d{{2}}\)?{_OPT_SEP})\d{{4,5}}{_SEP}\d{{4}}",
    ),
    "RU": (
        r"7",
        rf"(?:\(?\d{{3}}\)?{_OPT_SEP})\d{{3}}{_SEP}\d{{2}}{_SEP}\d{{2}}",
    ),
    "AU": (
        r"61",
        rf"0?\d{_OPT_SEP}\d{{4}}{_SEP}\d{{4}}",
    ),
    "MX": (
        r"52",
        rf"(?:\(?\d{{2}}\)?{_OPT_SEP})\d{{4}}{_SEP}\d{{4}}",
    ),
    "KR": (
        r"82",
        rf"0?\d{{1,2}}{_SEP}\d{{3,4}}{_SEP}\d{{4}}",
    ),
    "SA": (
        r"966",
        rf"0?\d{{2}}{_SEP}\d{{3}}{_SEP}\d{{4}}",
    ),
    "ZA": (
        r"27",
        rf"0?\d{{2}}{_SEP}\d{{3}}{_SEP}\d{{4}}",
    ),
}


def _build_country_pattern(code: str, local: str, required: bool = False) -> str:
    prefix = rf"(?:{code}{_SEP})" if required else rf"(?:{code}{_SEP})?"
    return rf"{prefix}(?:{local}){_EXT}"


PHONE_PATTERNS: dict[str, re.Pattern] = {
    country: re.compile(
        rf"\b{_build_country_pattern(code, local, *rest)}\b",
        re.IGNORECASE,
    )
    for country, (code, local, *rest) in _PHONE_FORMATS.items()
}

PHONE_NUMBER_RE = re.compile(
    r"\b(?:"
    + "|".join(
        _build_country_pattern(code, local, *rest)
        for _, (code, local, *rest) in _PHONE_FORMATS.items()
    )
    + r")\b",
    re.IGNORECASE,
)


def match_phone(text: str) -> list[tuple[str, str]]:
    """
    Returns list of (country, matched_span) for all matches.
    Checks per-country patterns so the matching country is identified.
    """
    results = []
    for country, pattern in PHONE_PATTERNS.items():
        for m in pattern.finditer(text):
            results.append((country, m.group(0)))
    return results


# =============================================================================
# SPAN MERGING
# Merges adjacent ADDRESS spans within _MERGE_GAP characters.
# Handles cases like "123 Main St, Suite 200, New York, NY 10001"
# producing one span instead of three.
# =============================================================================

_MERGE_GAP = 15

TITLE_CASE_WORDS_RE = re.compile(r"\b[A-Z][a-z]+(?:[\s,]+[A-Z][a-z]+)*\b")
STATE_ABBR_RE = re.compile(r"\b[A-Z]{2,4}\b")
# =============================================================================
# SPAN MERGING
# =============================================================================

_MERGE_GAP = 15

TITLE_CASE_WORDS_RE = re.compile(r"\b[A-Z][a-z]+(?:[\s,]+[A-Z][a-z]+)*\b")
STATE_ABBR_RE = re.compile(r"\b[A-Z]{2,4}\b")

# Merge-group constants
_GRP_ADDRESS = "ADDRESS"
_GRP_PHONE = "PHONE"
_GRP_NONE = "NONE"  # never merges with anything


def _gap_has_city_state(text: str, gap_start: int, gap_end: int) -> bool:
    """Return True if the gap between two spans contains a city/state fragment."""
    gap = text[gap_start:gap_end]
    return bool(TITLE_CASE_WORDS_RE.search(gap) or STATE_ABBR_RE.search(gap))


def _merge_spans(
    spans: list[tuple[int, int, str, str]],  # (start, end, label, group)
    text: str,
    gap: int = _MERGE_GAP,
) -> list[tuple[str, int, int, str]]:
    """
    Merge adjacent spans that share the same merge-group.
    ADDRESS spans get an extended gap when the intervening text looks like
    a city / state fragment (title-case words or state abbreviations).
    PHONE spans (_GRP_PHONE) never merge with anything.
    """
    if not spans:
        return []

    spans = sorted(spans, key=lambda x: x[0])
    merged: list[tuple[str, int, int, str]] = []

    cur_start, cur_end, cur_label, cur_group = spans[0]

    for start, end, label, group in spans[1:]:
        # Never merge if either span opted out
        if cur_group == _GRP_NONE or group == _GRP_NONE:
            merged.append((text[cur_start:cur_end], cur_start, cur_end, cur_label))
            cur_start, cur_end, cur_label, cur_group = start, end, label, group
            continue

        # Only merge spans in the same group
        if cur_group != group:
            merged.append((text[cur_start:cur_end], cur_start, cur_end, cur_label))
            cur_start, cur_end, cur_label, cur_group = start, end, label, group
            continue

        raw_gap = start - cur_end
        if cur_group == _GRP_ADDRESS:
            # Allow a larger gap when the intervening text looks like city/state
            effective_gap = 40 if _gap_has_city_state(text, cur_end, start) else gap
        else:
            effective_gap = gap

        if raw_gap <= effective_gap:
            cur_end = max(cur_end, end)
        else:
            merged.append((text[cur_start:cur_end], cur_start, cur_end, cur_label))
            cur_start, cur_end, cur_label, cur_group = start, end, label, group

    merged.append((text[cur_start:cur_end], cur_start, cur_end, cur_label))
    return merged


# =============================================================================
# EXTRACT SPANS
# =============================================================================


def extract_spans(text: str) -> list[tuple[str, int, int, str]]:
    """
    Extract ADDRESS / PHONE spans from text.
    Returns (match_text, start, end, label) tuples.

    Merge rules
    -----------
    ADDRESS group  : STREET_ADDRESS_RE, UNIT_RE, ADDRESS_COMPONENT_RE, ZIP_CODE_RE
                     These merge with each other.  The gap is widened when the
                     intervening text contains title-case words (city names) or
                     state abbreviations so that full postal addresses collapse
                     into a single span.
    PHONE group    : PHONE_NUMBER_RE — never merges with address spans or with
                     other phone spans (each number stays its own span).
    """
    if not text:
        return []

    # (start, end, label, merge_group)
    raw: list[tuple[int, int, str, str]] = []

    address_label = LABELS.ADDRESS.value

    for pat in (STREET_ADDRESS_RE, UNIT_RE, ADDRESS_COMPONENT_RE, ZIP_CODE_RE):
        for m in pat.finditer(text):
            raw.append((m.start(), m.end(), address_label, _GRP_ADDRESS))

    for m in PHONE_NUMBER_RE.finditer(text):
        raw.append((m.start(), m.end(), address_label, _GRP_PHONE))

    return _merge_spans(raw, text)
