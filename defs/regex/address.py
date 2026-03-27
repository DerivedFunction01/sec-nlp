from __future__ import annotations
import re
from defs.regex_lib import build_alternation
from defs.labels import LABELS


# =============================================================================
# ADDRESS TERMS
# =============================================================================

STREET_TERMS: list[str] = [
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
    rf"\b\d{{1,6}}\s+[A-Za-z0-9][\w\s\-']{{1,40}}\s+(?:{_street_terms})\b",
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


def _merge_spans(
    spans: list[tuple[int, int, str]], text: str, gap: int = _MERGE_GAP
) -> list[tuple[str, int, int, str]]:
    if not spans:
        return []
    spans = sorted(spans, key=lambda x: x[0])
    merged: list[tuple[str, int, int, str]] = []
    cur_start, cur_end, cur_label = spans[0]
    for start, end, label in spans[1:]:
        if start - cur_end <= gap:
            cur_end = max(cur_end, end)
        else:
            merged.append((text[cur_start:cur_end], cur_start, cur_end, cur_label))
            cur_start, cur_end, cur_label = start, end, label
    merged.append((text[cur_start:cur_end], cur_start, cur_end, cur_label))
    return merged


# =============================================================================
# EXTRACT SPANS
# =============================================================================


def extract_spans(text: str) -> list[tuple[str, int, int, str]]:
    """
    Extract ADDRESS spans from text.
    Returns (match_text, start, end, label) tuples.
    Merges adjacent spans so street + unit + zip collapse into one span.
    """
    if not text:
        return []

    spans: list[tuple[int, int, str]] = []

    for pat in (
        STREET_ADDRESS_RE,
        UNIT_RE,
        ADDRESS_COMPONENT_RE,
        ZIP_CODE_RE,
        PHONE_NUMBER_RE,
    ):
        for m in pat.finditer(text):
            spans.append((m.start(), m.end(), LABELS.ADDRESS.value))

    return _merge_spans(spans, text)
