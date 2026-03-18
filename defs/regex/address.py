from __future__ import annotations
import re
from defs.regex_lib import build_alternation
from defs.labels import LABELS


# =============================================================================
# ADDRESS TERMS (ported from text_cleaner.py)
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

ZIP_CODE_RE = re.compile(r"\b\d{5}(?:[- ]\d{4})?\b")

# "123 Main St", "Suite 200", "Unit 12"
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

_SEP = r"[-.\s]"
_OPT_SEP = r"[-.\s]?"
_EXT = r"(?:\s*(?:x|ext\.?)\s*\d{1,5})?"

# Each entry: (country_code, local_pattern)
# Local pattern must enforce block lengths to avoid date/IP false positives
_PHONE_FORMATS = {
    "US_CA": (
        r"1",
        # (NXX) NXX-XXXX — 3+3+4 digits
        rf"(?:\(?\d{{3}}\)?{_OPT_SEP})\d{{3}}{_SEP}\d{{4}}",
    ),
    "UK": (
        r"44",
        # (0XX) XXXX XXXX — 2-4 + 3-4 + 3-4
        rf"(?:\(?0?\d{{2,4}}\)?{_OPT_SEP})\d{{3,4}}{_SEP}\d{{3,4}}",
    ),
    "FR": (
        r"33",
        # 0X XX XX XX XX — 1+2+2+2+2
        rf"0?\d{_OPT_SEP}\d{{2}}{_SEP}\d{{2}}{_SEP}\d{{2}}{_SEP}\d{{2}}",
    ),
    "DE": (
        r"49",
        # Only match if +49 is present, don't try bare local
        rf"\d{{2,5}}{_SEP}\d{{3,8}}",  # drop the 0? prefix match
    ),
    "IT": (
        r"39",
        # 0XX XXXXXXX — area (2-4) + local (4-8)
        rf"0?\d{{1,4}}{_SEP}\d{{4,8}}",
    ),
    "JP": (
        r"81",
        # 0X-XXXX-XXXX — 1-4 + 4 + 4
        rf"0?\d{{1,4}}{_SEP}\d{{4}}{_SEP}\d{{4}}",
    ),
    "CN": (
        r"86",
        # mobile: 1XX XXXX XXXX — 3+4+4
        # landline: 0XX-XXXX-XXXX — 3+4+4
        rf"(?:1\d{{2}}{_SEP}\d{{4}}{_SEP}\d{{4}}|0\d{{2,3}}{_SEP}\d{{4}}{_SEP}\d{{4}})",
    ),
    "IN": (
        r"91",
        # XXXXX XXXXX — 5+5
        rf"\d{{5}}{_SEP}\d{{5}}",
    ),
    "BR": (
        r"55",
        # (XX) XXXXX-XXXX — 2+5+4
        rf"(?:\(?\d{{2}}\)?{_OPT_SEP})\d{{4,5}}{_SEP}\d{{4}}",
    ),
    "RU": (
        r"7",
        # (XXX) XXX-XX-XX — 3+3+2+2
        rf"(?:\(?\d{{3}}\)?{_OPT_SEP})\d{{3}}{_SEP}\d{{2}}{_SEP}\d{{2}}",
    ),
    "AU": (
        r"61",
        # 0X XXXX XXXX — 1+4+4
        rf"0?\d{_OPT_SEP}\d{{4}}{_SEP}\d{{4}}",
    ),
    "MX": (
        r"52",
        # (XX) XXXX-XXXX — 2+4+4
        rf"(?:\(?\d{{2}}\)?{_OPT_SEP})\d{{4}}{_SEP}\d{{4}}",
    ),
    "KR": (
        r"82",
        # 0XX-XXXX-XXXX — 2+4+4
        rf"0?\d{{1,2}}{_SEP}\d{{3,4}}{_SEP}\d{{4}}",
    ),
    "SA": (
        r"966",
        # 0XX XXX XXXX — 2+3+4
        rf"0?\d{{2}}{_SEP}\d{{3}}{_SEP}\d{{4}}",
    ),
    "ZA": (
        r"27",
        # 0XX XXX XXXX — 2+3+4
        rf"0?\d{{2}}{_SEP}\d{{3}}{_SEP}\d{{4}}",
    ),
}


def _build_country_pattern(code: str, local: str) -> str:
    return (
        rf"(?:{code}{_SEP})?"  # optional country code
        rf"(?:{local})"  # local format
        rf"{_EXT}"  # optional extension
    )


# Per-country compiled regexes for testing/debugging
PHONE_PATTERNS = {
    country: re.compile(
        rf"\b{_build_country_pattern(code, local)}\b",
        re.IGNORECASE,
    )
    for country, (code, local) in _PHONE_FORMATS.items()
}

# Combined pattern for NER inference
PHONE_NUMBER_RE = re.compile(
    r"\b(?:"
    + "|".join(
        _build_country_pattern(code, local)
        for _, (code, local) in _PHONE_FORMATS.items()
    )
    + r")\b",
    re.IGNORECASE,
)


def match_phone(text: str) -> list[tuple[str, str]]:
    """
    Returns list of (country, matched_span) for all matches.
    Checks per-country patterns so the matching group is identified.
    """
    results = []
    for country, pattern in PHONE_PATTERNS.items():
        for m in pattern.finditer(text):
            results.append((country, m.group(0)))
    return results


def extract_spans(text: str) -> list[tuple[int, int, str]]:
    """
    Extract ADDRESS spans from text using address-specific rules.
    Returns (start, end, label) tuples.
    """
    if not text:
        return []

    spans: list[tuple[int, int, str]] = []

    for m in STREET_ADDRESS_RE.finditer(text):
        spans.append((m.start(), m.end(), LABELS.ADDRESS.value))

    for m in UNIT_RE.finditer(text):
        spans.append((m.start(), m.end(), LABELS.ADDRESS.value))

    for m in ADDRESS_COMPONENT_RE.finditer(text):
        spans.append((m.start(), m.end(), LABELS.ADDRESS.value))

    for m in ZIP_CODE_RE.finditer(text):
        spans.append((m.start(), m.end(), LABELS.ADDRESS.value))

    for m in PHONE_NUMBER_RE.finditer(text):
        spans.append((m.start(), m.end(), LABELS.ADDRESS.value))

    return spans
