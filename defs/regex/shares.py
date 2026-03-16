from typing import List

from defs.regex_lib import build_compound, build_regex


_SHARE_UNITS_PREFIXES = [
    "trust",
    "REIT",
    "operating",
    r"limited\s+partnership",
    "depositary",
    "fractional",
    "stock",
]

_SHARE_CORE = [
    r"shares?",
    r"stocks?",
    r"warrants?",
    r"options?",
    r"rights?",
    r"RSUs?",
    r"PSUs?",
    r"DSUs?",
    r"SARs?",
    r"grants?",
    r"awards?",
]

_SHARE_QUALIFIERS = [
    r"preferred",
    r"common",
    r"ordinary",
    r"treasury",
    r"restricted",
    r"outstanding",
]

_SHARE_QUALIFIED_CORE = [
    r"stocks?",
    r"shares?",
]

_SHARE_QUALIFIED = [
    build_compound(
        prefix=_SHARE_QUALIFIERS,
        core=_SHARE_QUALIFIED_CORE,
        sep_prefix=r"\s+",
    ),
    # restricted can also qualify units
    build_compound(
        prefix=r"restricted",
        core=r"units?",
        sep_prefix=r"\s+",
    ),
]
# units? only matches when preceded by an equity qualifier
_SHARE_UNITS = build_compound(
    prefix=_SHARE_UNITS_PREFIXES,
    core=r"units?",
    sep_prefix=r"\s+",
)

SHARE_TERMS: List[str] = _SHARE_CORE + _SHARE_QUALIFIED + [_SHARE_UNITS]
