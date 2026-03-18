import re

from defs.labels import LABELS
from defs.regex_lib import YEAR_REGEX, build_alternation, NUMBER_RANGE_STR

# =============================================================================
# FRAGMENT STRINGS
# Reusable building blocks — all plain strings, not compiled patterns.
# =============================================================================

MONTHS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Sept",
    "Oct",
    "Nov",
    "Dec",
]

_MONTH_STR = build_alternation(MONTHS) + r"[a-z]*\.?"
_YEAR_STR = r"(?:19|20)\d{2}"
_FISCAL_YEAR_NUM_STR = rf"(?:{_YEAR_STR}|\d{{2}})"
_DAY_STR = r"\d{1,2}(?:st|nd|rd|th)?"
_OPT_COMMA = r"(?:,)?"

# =============================================================================
# DATE PATTERNS
# =============================================================================

DATE_MDY = re.compile(
    rf"\b(?:{_MONTH_STR})\s+{_DAY_STR}{_OPT_COMMA}\s+{_YEAR_STR}\b",
    re.IGNORECASE,
)

DATE_DMY = re.compile(
    rf"\b{_DAY_STR}\s+(?:of\s+)?(?:{_MONTH_STR}){_OPT_COMMA}\s+{_YEAR_STR}\b",
    re.IGNORECASE,
)

DATE_MD = re.compile(
    rf"\b(?:{_MONTH_STR})\s+{_DAY_STR}{_OPT_COMMA}(?!\d)",
    re.IGNORECASE,
)

DATE_DM = re.compile(
    rf"(?<!\d){_DAY_STR}\s+(?:of\s+)?(?:{_MONTH_STR})\b",
    re.IGNORECASE,
)

SLASH_DATE = re.compile(
    r"\b"
    r"(?:"
    r"\d{1,2}/\d{1,2}/\d{2,4}"  # 12/31/2001 or 12/31/01
    r"|"
    r"\d{1,2}/\d{4}"  # 12/2001 only
    r")"
    r"\b",
)

YEAR_RANGE = re.compile(rf"\b({_YEAR_STR})-(\d{{2}})\b")

DATE_YEAR = YEAR_REGEX

# =============================================================================
# FISCAL / QUARTER PATTERNS
# =============================================================================

FISCAL_YEAR = re.compile(
    rf"\b(?:fiscal|fy)\s*(?:year\s*)?{_FISCAL_YEAR_NUM_STR}\b",
    re.IGNORECASE,
)

QUARTER = re.compile(
    rf"\bQ[1-4]\s*(?:FY\s*)?{_FISCAL_YEAR_NUM_STR}\b",
    re.IGNORECASE,
)

# =============================================================================
# DURATION PATTERN
# =============================================================================

_TIME_UNITS_STR = build_alternation(
    [
        r"days?",
        r"weeks?",
        r"months?",
        r"quarters?",
        r"years?",
        r"yrs?",
        r"hours?",
        r"hrs?",
        r"minutes?",
        r"mins?",
        r"seconds?",
        r"secs?",
    ]
)

DURATION = re.compile(
    rf"\b({NUMBER_RANGE_STR})\s*(?:-|\s+)\s*(?:{_TIME_UNITS_STR})\b",
    re.IGNORECASE,
)

# =============================================================================
# EXTRACT SPANS
# Priority order matters: longer/more specific patterns first to win overlap
# resolution — e.g. "May 31, 2005" beats bare "2005".
# =============================================================================

_PATTERNS = [
    DATE_MDY,
    DATE_DMY,
    SLASH_DATE,
    DATE_MD,
    DATE_DM,
    YEAR_RANGE,
    QUARTER,
    FISCAL_YEAR,
    DURATION,
    DATE_YEAR,
]


def extract_spans(text: str) -> list[tuple[int, int, str]]:
    """
    Extract TIME spans from text.
    Returns (start, end, label) tuples.
    """
    if not text:
        return []

    raw_matches: list[tuple[int, int]] = []
    for pat in _PATTERNS:
        for m in pat.finditer(text):
            raw_matches.append((m.start(), m.end()))

    if not raw_matches:
        return []

    # Prefer longer spans, resolve overlaps
    raw_matches.sort(key=lambda x: (-(x[1] - x[0]), x[0]))

    chosen: list[tuple[int, int]] = []
    for start, end in raw_matches:
        if not any(not (end <= cs or start >= ce) for cs, ce in chosen):
            chosen.append((start, end))

    chosen.sort(key=lambda x: x[0])
    return [(s, e, LABELS.TIME.value) for s, e in chosen]
