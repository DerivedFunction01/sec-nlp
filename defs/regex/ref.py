import re
from defs.regex_lib import build_alternation, build_regex

# --- ACCOUNTING STANDARD ISSUERS ---
STANDARDS_TERMS = [
    r"SFAS",
    r"FAS",
    r"ASU",
    r"ASC",
    r"IFRS",
    r"IAS",
    r"IFRIC",
    r"SIC",
    r"EITF",
    r"SOP",
    r"FSP",
    r"FIN",
    r"APB",
    r"SFAC",
    r"GAAP",
    r"TB",
]

GUIDANCE_OBJECT_TYPES = [
    r"Guidance",
    r"Standards?",
    r"Amendments?",
    r"Statements?",
    r"Provisions?",
    r"Regulations?",
    r"Abstracts?",
    r"Opinions?",
    r"Codifications?",
    r"Pronouncements?",
    r"Interpretations?",
    r"Bulletins?",
    r"Frameworks?",
    r"Concept\s+Statements?",
    r"Clarifications?",
    r"Rules?",
    r"Principles?",
    r"Topic",    
    r"Subtopic",
    r"Paragraphs?",
    r"Sections?",
    r"Subsections?",
    r"Issue",
]

# --- EXHIBIT / DOCUMENT REFERENCE NOUNS ---
EXHIBIT_NOUNS = [
    r"exhibits?",
    r"notes?",
    r"appendix",
    r"appendices",
    r"schedules?",
    r"sections?",
    r"subsections?",
    r"clauses?",
    r"articles?",
    r"items?",
    r"figures?",
    r"charts?",
    r"tables?",
    r"pages?",
    r"pp\.",
    r"p\.",
    r"chapters?",
    r"annexes?",
    r"addenda?",
    r"addendums?",
]

_STANDARDS_FRAGMENT = build_alternation(STANDARDS_TERMS)
_GUIDANCE_FRAGMENT = build_alternation(GUIDANCE_OBJECT_TYPES)
_EXHIBIT_FRAGMENT = build_alternation(EXHIBIT_NOUNS)

# Matches: ASC 842-10-25-1, SFAS 133, ASU 2016-13, EITF 00-19, FIN 48,
#          "Guidance No. 123", "Opinion No. 45-B"
_STANDARD_ID_PATTERN = (
    rf"(?:{_STANDARDS_FRAGMENT}|{_GUIDANCE_FRAGMENT})"
    rf"(?:\s+(?:{_STANDARDS_FRAGMENT}|{_GUIDANCE_FRAGMENT}))*"  # e.g. FASB ASC, FASB Statement
    r"(?:\s+Issue)?"
    r"(?:\s+No\.?)?"
    r"\s*\d+(?:[\.\-]\d+)*"
    r"[A-Z]?"
)

# Matches: Exhibit 10.2, Note 5, Schedule A-3, Page 10, p. 5, pp. 20-25
_EXHIBIT_PATTERN = (
    rf"(?:{_EXHIBIT_FRAGMENT})"
    r"(?:\s*No\.?)?"
    r"\s*\d(?:[\d\.\-]*\d)?"
    r"[A-Z]?"
    r"(?:"
    r"\s*(?:,?\s*(?:and|or|&)|,|to|through)\s*"
    r"\d(?:[\d\.\-]*\d)?[A-Z]?"
    r")*"
)

# --- COMBINED REFERENCE PATTERN ---
REFERENCE_PATTERN = re.compile(
    rf"\b(?:{_STANDARD_ID_PATTERN}|{_EXHIBIT_PATTERN})",
    re.IGNORECASE,
)
