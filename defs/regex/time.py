# Year_regex YEAR_REGEX from regex_lib

# Date and Year Patterns
import re

from defs.regex_lib import YEAR_REGEX, build_alternation


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
months_pattern_str = build_alternation(MONTHS) + r"[a-z]*\.?"

DATE_MD = re.compile(
    rf"\b(?:{months_pattern_str})\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,)?(?!\d)",
    re.IGNORECASE,
)

DATE_DM = re.compile(
    rf"(?<!\d)(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?(?:{months_pattern_str})\b",
    re.IGNORECASE,
)

DATE_YEAR = YEAR_REGEX
SLASH_DATE = re.compile(r"\b(?:\d{1,2}/)+\d{2,4}\b")
YEAR_RANGE = re.compile(r"\b((?:19|20)\d{2})-(\d{2})\b")
