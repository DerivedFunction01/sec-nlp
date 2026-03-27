from __future__ import annotations
import re
from defs.labels import LABELS
from defs.regex_lib import YEAR_RE, build_alternation, NUMBER_RANGE_STR

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

DATE_YEAR = YEAR_RE

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
# Clock time: 12:30 PM, 9:00 AM, 23:59, etc.
CLOCK_TIME = re.compile(
    r"\b(?:[01]?\d|2[0-3]):[0-5]\d(?::[0-5]\d)?(?:\s*[AP]M)?\b",
    re.IGNORECASE,
)


OCLOCK_TIME = re.compile(
    rf"\b(?:\d{{1,2}})\s+o'?clock\b",
    re.IGNORECASE,
)

# =============================================================================
# EXTRACT SPANS
# Priority order matters: longer/more specific patterns first to win overlap
# resolution — e.g. "May 31, 2005" beats bare "2005".
# =============================================================================

# Tier 1: Full date+year forms (most specific)
_TIER_1 = [DATE_MDY, DATE_DMY, SLASH_DATE, YEAR_RANGE, CLOCK_TIME, OCLOCK_TIME]

# Tier 2: Fiscal/quarter (specific enough to beat bare years)
_TIER_2 = [QUARTER, FISCAL_YEAR]

# Tier 3: Partial dates (no year — only used if no tier-1/2 match covers the span)
_TIER_3 = [DATE_MD, DATE_DM]

# Tier 4: Duration (number + unit — must not swallow a year that's part of a date)
_TIER_4 = [DURATION]

# Tier 5: Bare year (last resort — only if nothing else claimed the span)
_TIER_5 = [DATE_YEAR]

_TIERS = [_TIER_1, _TIER_2, _TIER_3, _TIER_4, _TIER_5]


def _overlaps(start: int, end: int, chosen: list[tuple[str, int, int]]) -> bool:
    """True if [start, end) overlaps any already-chosen span."""
    return any(start < ce and end > cs for _, cs, ce in chosen)

# =============================================================================
# SPAN MERGING
# =============================================================================

_MERGE_GAP = 10  # tighter than address — time components sit close together

_TIME_CONNECTORS_RE = re.compile(
    r"^[\s,\-–at@<>]+$",  # only whitespace/punctuation/connectors between spans
    re.IGNORECASE,
)

def _merge_time_spans(
    spans: list[tuple[str, int, int, str]],
    text: str,
    gap: int = _MERGE_GAP,
) -> list[tuple[str, int, int, str]]:
    """
    Merge adjacent TIME spans when the gap between them is only
    whitespace, punctuation, or connector words like 'at'.
    """
    if not spans:
        return []

    merged: list[tuple[str, int, int, str]] = []
    cur_text, cur_start, cur_end, cur_label = spans[0]

    for next_text, next_start, next_end, next_label in spans[1:]:
        raw_gap = next_start - cur_end
        if raw_gap <= gap and _gap_is_time_connector(text, cur_end, next_start):
            # Extend the current span to absorb the next one
            cur_end = next_end
            cur_text = text[cur_start:cur_end]
        else:
            merged.append((cur_text, cur_start, cur_end, cur_label))
            cur_text, cur_start, cur_end, cur_label = (
                next_text,
                next_start,
                next_end,
                next_label,
            )

    merged.append((cur_text, cur_start, cur_end, cur_label))
    return merged


def _gap_is_time_connector(text: str, gap_start: int, gap_end: int) -> bool:
    """True if the text between two time spans is just whitespace/punctuation/connector words."""
    gap = text[gap_start:gap_end]
    return bool(_TIME_CONNECTORS_RE.match(gap))


def extract_spans(text: str) -> list[tuple[str, int, int, str]]:
    if not text:
        return []

    chosen: list[tuple[str, int, int]] = []

    for tier in _TIERS:
        candidates: list[tuple[str, int, int]] = []
        for pat in tier:
            for m in pat.finditer(text):
                candidates.append((m.group(0), m.start(), m.end()))

        candidates.sort(key=lambda x: (-(x[2] - x[1]), x[1]))

        for match_text, start, end in candidates:
            if not _overlaps(start, end, chosen):
                chosen.append((match_text, start, end))

    chosen.sort(key=lambda x: x[1])
    labeled = [(t, s, e, LABELS.TIME.value) for t, s, e in chosen]

    # Collapse adjacent time spans separated only by whitespace/punctuation
    return _merge_time_spans(labeled, text)
