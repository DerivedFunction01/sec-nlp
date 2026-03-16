from __future__ import annotations
from enum import Enum
from defs.regex_lib import build_compound


# =============================================================================
# TIERS & ENUMS
# =============================================================================


class LocationTier(Enum):
    PHYSICAL = "physical"  # facilities, offices, warehouses, plants
    GEO = "geo"  # countries, regions, states, cities
    ADDRESS_UNIT = "address_unit"  # floors, suites, units, buildings


# =============================================================================
# LOCATION TERMS
# =============================================================================

# Physical assets / facilities
PHYSICAL_LOCATION_TERMS: set[str] = {
    # Facilities
    r"facilit(?:y|ies)",
    r"plants?",
    r"factories|factory",
    r"warehouses?",
    r"laborator(?:y|ies)",
    r"labs?",
    # Offices / Commercial
    r"offices?",
    r"stores?",
    r"outlets?",
    r"showrooms?",
    r"branch(?:es)?",
    r"headquarters",
    # Industrial / Energy
    r"mines?",
    r"refiner(?:ies|y)",
    r"terminals?",
    r"depots?",
    r"wells?",
    r"rigs?",
    r"pipelines?",
    # Land / Agriculture
    r"farms?",
    r"ranches?",
    r"fields?",
    # General
    r"sites?",
    r"locations?",
    r"centers?",
    r"propert(?:ies|y)",
    r"premises",
    r"campuses?",
}

# Geographic coverage
GEO_LOCATION_TERMS: set[str] = {
    # Top-level
    r"continents?",
    r"countr(?:ies|y)",
    r"nations?",
    # Sub-national
    r"states?",
    r"provinces?",
    r"territor(?:ies|y)",
    r"regions?",
    r"districts?",
    r"counties|county",
    r"parishes?",
    r"prefectures?",
    # Municipal
    r"municipalit(?:ies|y)",
    r"cit(?:ies|y)",
    r"towns?",
    r"villages?",
    r"boroughs?",
    # General
    r"areas?",
    r"zones?",
    r"sectors?",
    r"jurisdictions?",
}

# =============================================================================
# REGEX-CONCATENATED TERMS
# =============================================================================

# Flat union for matching "number + location term" patterns
LOCATION_TERMS: set[str] = (
    PHYSICAL_LOCATION_TERMS | GEO_LOCATION_TERMS
)

# Optional: build compound patterns for multi-word physical locations if needed
PHYSICAL_COMPOUNDS: set[str] = {
    build_compound([r"distribution", r"fulfillment", r"data", r"call", r"manufacturing"], r"centers?"),
}
