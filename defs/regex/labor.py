from __future__ import annotations
from enum import Enum
import re
from defs.labels import LABELS
from defs.regex_lib import (
    NUMBER_PATTERN_STR,
    NUMBER_RANGE_STR,
    build_alternation,
    build_compound,
    build_regex,
    to_build_alternation,
    SENTENCE_SPLIT_PATTERN,
)


# =============================================================================
# TIERS & ENUMS
# =============================================================================


class WorkerTier(Enum):
    GENERIC = "generic"
    INDUSTRY = "industry"
    OCCUPATION = "occupation"
    MODIFIER = "modifier"
    PRONOUN = "pronoun"


class IndustryGroup(Enum):
    HEAVY = "heavy"
    MANUFACTURING = "manufacturing"
    TRANSPORT = "transport"
    SERVICE = "service"
    NATURAL = "natural"


# =============================================================================
# INDUSTRY PREFIX TERMS (grouped by IndustryGroup)
# =============================================================================

INDUSTRY_PREFIX_TERMS: dict[IndustryGroup, list[str]] = {
    IndustryGroup.HEAVY: [
        r"steel",
        r"aluminum",
        r"iron",
        r"metal",
        r"coal",
        r"mining",
        r"mine",
        r"oil",
        r"gas",
        r"energy",
        r"chemical",
        r"asbestos",
        r"rubber",
        r"glass",
        r"meatpacking",
        r"tobacco",
    ],
    IndustryGroup.MANUFACTURING: [
        r"automotive",
        r"auto",
        r"shipbuilding",
        r"electronics",
        r"electrical",
        r"manufacturing",
        r"industrial",
        r"packaging",
        r"textile",
        r"pulp",
        r"paper",
        r"mill",
        r"plant",
        r"heat insulator",
        r"frost insulator",
    ],
    IndustryGroup.TRANSPORT: [
        r"aviation",
        r"rail",
        r"railroad",
        r"transit",
        r"trucking",
        r"transport",
        r"transportation",
        r"maritime",
        r"longshore",
        r"dock",
        r"port",
        r"warehouse",
        r"postal",
    ],
    IndustryGroup.SERVICE: [
        r"retail",
        r"food",
        r"hospitality",
        r"hotel",
        r"healthcare",
        r"pharmaceutical",
        r"telecommunications",
        r"communication",
        r"service",
    ],
    IndustryGroup.NATURAL: [
        r"agriculture",
        r"agricultural",
        r"farm",
        r"forestry",
        r"timber",
        r"building",
        r"construction",
    ],
}

# Flat list for regex building
INDUSTRY_PREFIX_TERMS_FLAT: list[str] = [
    term for group in IndustryGroup for term in INDUSTRY_PREFIX_TERMS[group]
]


def _regex_to_plain(term: str) -> str:
    """Strip regex syntax from a pattern to get a plain substitution string."""
    plain = re.sub(r"\(.*?\)|\[.*?\]|\?|\\", "", term).strip().lower()
    return plain


def _generate_industry_worker_pool() -> dict[str, list[str]]:
    """Dynamically generate industry worker terms from INDUSTRY_PREFIX_TERMS groups."""
    pool = {}
    for group in IndustryGroup:
        workers = []
        for term in INDUSTRY_PREFIX_TERMS[group]:
            plain = _regex_to_plain(term)
            if plain:
                workers.append(f"{plain} workers")
        pool[group.value] = workers
    return pool


def _generate_occupation_pool() -> dict[str, list[str]]:
    """Dynamically generate plain occupation terms from OCCUPATION_GROUP_TERMS groups."""
    pool = {}
    for group, terms in OCCUPATION_GROUP_TERMS.items():
        occupations = []
        for term in terms:
            plain = _regex_to_plain(term)
            if plain:
                occupations.append(plain)
        pool[group.value] = occupations
    return pool


# =============================================================================
# WORKER TERMS
# =============================================================================

GENERIC_WORKER_TERMS: set[str] = {
    r"workers?",
    r"employees?",
    r"labo(?:u)?rers?",
    r"staff",
    r"personnel",
    r"members?"
}

WORKER_TYPES: set[str] = {
    r"part[- ]time",
    r"full[- ]time",
    r"contract",
    r"seasonal",
    r"specialized",
    r"temporary",
    r"permanent",
    r"salaried",
    r"hourly",
}


class OccupationGroup(Enum):
    HEALTHCARE = "healthcare"
    AVIATION = "aviation"
    TRANSPORT = "transport"
    TRADES = "trades"
    PUBLIC_SAFETY = "public_safety"
    HOSPITALITY = "hospitality"
    MEDIA = "media"
    OTHER = "other"


OCCUPATION_GROUP_TERMS = {
    OccupationGroup.HEALTHCARE: [r"nurses?", r"doctors?", r"surgeons?", r"physicians?"],
    OccupationGroup.AVIATION: [
        r"pilots?",
        r"flight\s+attendants?",
        r"air\s+traffic\s+controllers",
    ],
    OccupationGroup.TRANSPORT: [
        r"drivers?",
        r"truck\s+drivers",
        r"delivery\s+drivers",
        r"taxi\s+drivers",
        r"cargo\s+drivers",
    ],
    OccupationGroup.TRADES: [
        r"electricians?",
        r"carpenters?",
        r"plumbers?",
        r"welders?",
        r"pipefitters?",
        r"boilermakers?",
        r"millwrights?",
        r"fabricators?",
        r"assemblers?",
        r"dispatchers?",
        r"mechanics?",
        r"engineers?",
    ],
    OccupationGroup.PUBLIC_SAFETY: [
        r"police",
        r"sheriffs?",
        r"security\s+guards",
        r"firefighters",
        r"security\s+officers",
    ],
    OccupationGroup.HOSPITALITY: [
        r"chefs?",
        r"cooks?",
        r"cookers?",
        r"waiters?",
        r"bartenders?",
        r"cashiers?",
    ],
    OccupationGroup.MEDIA: [r"actors?", r"writers?", r"directors?", r"producers?", r"composers?", r"filmmakers?"],
    OccupationGroup.OTHER: [
        r"technicians?",
        r"operators?",
        r"instructors?",
        r"custodians?",
        r"janitors?",
        r"miners?",
        r"researchers?",
        r"scientists?",
    ],
}

OCCUPATION_TERMS = {t for group in OCCUPATION_GROUP_TERMS.values() for t in group}


INDUSTRY_WORKER_TERMS: set[str] = {
    build_compound(
        INDUSTRY_PREFIX_TERMS_FLAT,
        r"workers?",
        sep_prefix=r"\s*",
    ),
}

# Full union for regex matching
WORKER_TERMS: set[str] = OCCUPATION_TERMS | INDUSTRY_WORKER_TERMS | GENERIC_WORKER_TERMS

PRONOUN_TERMS: list[str] = [r"whom?", r"them"]  # 50 of them, 50 of whom


# =============================================================================
# WORKER POOL (for NER augmentation / substitution)
# =============================================================================
#
# Substitution rules:
#   GENERIC    — safe everywhere, always grammatically valid
#   INDUSTRY   — safe when sentence has industry context; sample within same group
#                for semantic coherence (heavy -> heavy, transport -> transport)
#   OCCUPATION — safe when sentence has role context; sample within same group
#                for semantic coherence (healthcare -> healthcare, trades -> trades)
#   MODIFIER   — only substitutes within MODIFIER tier
#   PRONOUN    — never substitute INTO; only augment existing back-reference patterns
#
# Valid augmentation patterns:
#   [MODIFIER] + [GENERIC]      "500 part-time employees"  -> "500 seasonal workers"
#   [INDUSTRY] + [GENERIC]      "500 steel workers"        -> "500 coal workers"
#   [MODIFIER] + [OCCUPATION]   "500 part-time nurses"     -> "500 contract pilots"
#   [OCCUPATION]                "500 nurses"               -> "500 machinists"

WORKER_POOL: dict[WorkerTier, list[str] | dict[str, list[str]]] = {
    WorkerTier.GENERIC: [
        "employees",
        "workers",
        "staff",
        "personnel",
        "laborers",
        "workforce",
        "associates",
    ],
    WorkerTier.INDUSTRY: _generate_industry_worker_pool(),  # keyed by IndustryGroup.value
    WorkerTier.OCCUPATION: _generate_occupation_pool(),  # keyed by OccupationGroup.value
    WorkerTier.MODIFIER: [
        "part-time",
        "full-time",
        "contract",
        "seasonal",
        "specialized",
        "temporary",
        "permanent",
        "salaried",
        "hourly",
    ],
    WorkerTier.PRONOUN: [
        "whom",
        "them",
    ],
}


# =============================================================================
# PERSONNEL EVENT TERMS
# =============================================================================

# Unambiguously personnel-related — safe to use standalone
PERSONNEL_EVENT_TERMS: set[str] = {
    r"furlough(?:s|ed|ing)?",
    r"hir(?:es?|ed|ing)",
    r"fir(?:es?|ed|ing)",
    r"layoffs?",
    r"lay(?:ing)?\s+off",
    r"laid\s+off",
    r"recruit(?:s|ed|ing|ment)?",
    r"redundanc(?:y|ies)",
    r"severance",
    r"turnover",
    r"attritions?",
    r"headcount\s+reductions?",
    r"job\s+cuts?",
    r"downsiz(?:es?|ed|ing)",
    r"employ(?:ed|s|ing)",
    r"headcount",
}

# Ambiguous — require nearby personnel context to be meaningful
# e.g. "eliminate debt"    vs "eliminate positions"
#      "reduce costs"      vs "reduce headcount"
#      "terminate lease"   vs "terminate employment"
#      "separate filing"   vs "separation package"
#      "retention bonus"   vs "retention of records"
#      "recall products"   vs "recall workers"
PERSONNEL_EVENT_TERMS_CONTEXT: set[str] = {
    r"eliminat(?:es?|ed|ing|ions?)",
    r"separat(?:es?|ed|ing|ions?)",
    r"reduc(?:es?|ed|ing|tions?)",
    r"terminat(?:es?|ed|ing|ions?)",
    r"retention",
    r"recall(?:s|ed|ing)?",
}

COVERAGE_VERBS = {r"unionized", r"covered", r"subject\s+to", r"under", r"affiliated"}

# Gap that avoids consuming numbers (words must start with non-digit)
non_numeric_gap = r"(?:[^\W\d][\w\.-]*\s+){0,3}"
personnel_event = to_build_alternation(PERSONNEL_EVENT_TERMS)

worker_term_pattern = to_build_alternation(WORKER_TERMS)
_WORKER_CONTEXT_REGEX = build_regex(WORKER_TERMS)

_LABOR_CONTEXT_REGEX = build_regex(
    list(WORKER_TERMS | PERSONNEL_EVENT_TERMS )
)

_COPULA_NUMBER_REGEX = re.compile(
    rf"\b({NUMBER_PATTERN_STR})\s+(?:are|were|is|was)\b",
    re.IGNORECASE,
)
_NUMBER_REGEX = re.compile(rf"\b({NUMBER_PATTERN_STR})\b")

_DEPT_TERMS = build_alternation(
    [
        r"sales",
        r"engineering",
        r"manufacturing",
        r"operations?",
        r"production",
        r"marketing",
        r"research",
        r"development",
        r"r&d",
        r"finance",
        r"accounting",
        r"technology",
        r"it",
        r"hr",
        r"human\s+resources",
        r"legal",
        r"administration",
        r"customer\s+services?",
        r"support",
        r"procurement",
        r"supply\s+chains?",
        r"logistics",
        r"quality",
        r"compliance",
        r"security",
    ]
)
_DEPT_IN_REGEX = re.compile(
    rf"\b({NUMBER_PATTERN_STR})\s+(?:(?:are|were|is|was)\s+)?(?:in|within|across)\s+({_DEPT_TERMS})\b",
    re.IGNORECASE,
)

# Heuristic: treat large counts as labor without requiring local worker context.
_LABOR_CONTEXT_THRESHOLD = 1000

WORKER_COUNT_REGEX = build_regex(
    [
        rf"{personnel_event}\s+{non_numeric_gap}({NUMBER_RANGE_STR})",
        rf"({NUMBER_RANGE_STR})\s+{non_numeric_gap}{worker_term_pattern}",
        rf"{worker_term_pattern}\s+{non_numeric_gap}({NUMBER_RANGE_STR})",
        rf"({NUMBER_RANGE_STR})\s+(?:(?:are|were|is|was)\s+)?{to_build_alternation(COVERAGE_VERBS)}",
    ]
)


def is_labor_copula_sentence(sentence: str) -> bool:
    """
    Returns True if sentence has a copula-number pattern and a worker term
    somewhere in the same sentence.
    Example: "of which 1000 are in China" -> True if sentence includes
    "employees/workers/etc".
    """
    if not sentence:
        return False
    if not _COPULA_NUMBER_REGEX.search(sentence):
        return False
    return bool(_WORKER_CONTEXT_REGEX.search(sentence))


def extract_spans(text: str) -> list[tuple[int, int, str]]:
    """
    Extract LABOR spans from text using labor-specific rules.
    Returns (start, end, label) tuples.
    """
    if not text:
        return []

    spans: list[tuple[int, int, str]] = []
    span_set: set[tuple[int, int, str]] = set()

    def _add_span(start: int, end: int) -> None:
        item = (start, end, LABELS.LABOR.value)
        if item in span_set:
            return
        span_set.add(item)
        spans.append(item)

    def _iter_sentences(src: str) -> list[tuple[int, int, str]]:
        out: list[tuple[int, int, str]] = []
        start = 0
        for m in SENTENCE_SPLIT_PATTERN.finditer(src):
            end = m.end()
            chunk = src[start:end]
            if chunk.strip():
                out.append((start, end, chunk))
            start = end
        tail = src[start:]
        if tail.strip():
            out.append((start, len(src), tail))
        return out

    def _number_value(num_text: str) -> int:
        if not num_text:
            return 0
        # If a range, take the first number as a proxy
        first = re.split(r"[-–—]|\\bto\\b", num_text, maxsplit=1)[0]
        try:
            return int(float(first.replace(",", "")))
        except ValueError:
            return 0

    for sent_start, _, sentence in _iter_sentences(text):
        # Strong patterns always apply
        for m in WORKER_COUNT_REGEX.finditer(sentence):
            _add_span(sent_start + m.start(), sent_start + m.end())

        has_worker_context = bool(_WORKER_CONTEXT_REGEX.search(sentence))

        for m in _COPULA_NUMBER_REGEX.finditer(sentence):
            num_val = _number_value(m.group(1))
            if has_worker_context or num_val >= _LABOR_CONTEXT_THRESHOLD:
                _add_span(sent_start + m.start(1), sent_start + m.end(1))

        if has_worker_context:
            for m in _DEPT_IN_REGEX.finditer(sentence):
                _add_span(sent_start + m.start(1), sent_start + m.end(1))

        # If sentence is labor-heavy, tag large standalone numbers
        if _LABOR_CONTEXT_REGEX.search(sentence):
            for m in _NUMBER_REGEX.finditer(sentence):
                num_val = _number_value(m.group(1))
                if num_val >= _LABOR_CONTEXT_THRESHOLD:
                    _add_span(sent_start + m.start(1), sent_start + m.end(1))

    return spans
