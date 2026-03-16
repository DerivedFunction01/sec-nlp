from __future__ import annotations
from enum import Enum
import re
from defs.regex_lib import build_alternation, build_compound, build_regex


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
PERSONNEL_EVENT_TERMS_SAFE: set[str] = {
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
