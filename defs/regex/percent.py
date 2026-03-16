import re

from defs.regex_lib import build_compound, to_build_alternation, build_regex

PCT_CHANGE_TERMS = [
    "increase",
    "decrease",
    "decline",
    "reduction",
    "growth",
    "gain",
    "loss",
    "change",
    "rise",
    "fall",
    "drop",
    "jump",
    "surge",
    "improvement",
    "deterioration",
    "uptick",
    "downtick",
]

PCT_RATE_MODIFIERS = [
    "effective",
    "nominal",
    "weighted average",
    "weighted",
    "annualized",
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
    "floating"
]

PCT_RATE_SUFFIX = [
    "rate",
    "rates",
    "yield",
    "yields",
]

PCT = [
    r"per[- ]cent",
    r"percentage\s+points?",
]

PCT_REGEX = build_regex(PCT)
PCT_SPACE = re.compile(r"(\d)\s+%", re.IGNORECASE)
PCT_RANGE = re.compile(
    rf"\b(\d+(?:\.\d+)?)\s*%?\s*(?:-|–|—|to)\s*(\d+(?:\.\d+)?)\s*(?:%|{to_build_alternation(PCT)})",
    re.IGNORECASE,
)


# Matches: "interest rate", "effective tax rate", "weighted average discount rate"
PCT_RATE_RE = build_regex(
    [
        build_compound(
            prefix=PCT_RATE_MODIFIERS,
            core=PCT_RATE_SUFFIX,
        ),
        build_compound(
            prefix=PCT_RATE_CORE,
            core=PCT_RATE_SUFFIX,
        ),
    ] + PCT_RATE_SUFFIX # 10% yield
)

# Change terms are simpler — no compound structure needed
PCT_CHANGE_RE = build_regex(PCT_CHANGE_TERMS)
