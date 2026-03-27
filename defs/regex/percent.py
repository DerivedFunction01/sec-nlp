import re

from defs.regex_lib import closest_distance_in_segment, to_build_alternation, build_regex, SENTENCE_SPLIT_RE
from defs.labels import LABELS

PCT_CHANGE_TERMS = [
    r"increas(?:es?|ed|ing)",
    r"decreas(?:es?|ed|ing)",
    r"declin(?:es?|ed|ing|ation)",
    r"reduc(?:es?|ed|ing|tion)",
    r"grow(?:ing|th)|grew",
    r"gain(?:ed|ing|s)?",
    r"loss(?:es?)?|los(?:e|ing)",
    r"chang(?:es?|ed|ing)",
    r"ris(?:e|ing)|rose",
    r"fall(?:ing)|fell",
    r"drop(?:ped|ping)",
    r"jump(?:ed|ing)",
    r"surg(?:es?|ed|ing)",
    r"improve(?:d|s|ment)?",
    r"deteriorat(?:es?|ed|ing|ion)",
    "uptick",
    "downtick",
    r"up",
    r"down",
]

PCT_CHANGE_POST_TERMS = [
    r"more",
    r"less",
    r"higher",
    r"greater",
    r"lower",
    r"smaller",
    r"fewer",    
    r"larger",    
]
PCT_RATE_MODIFIERS = [
    r"(?:in)?effective",
    r"nominal",
    r"weighted",
    r"annual(?:ized)?",
    r"daily",
    r"weekly",
    r"monthly",
    r"quarterly",
    r"yearly",
    r"average",
    r"applicable",
    r"stated",
    r"blended",
    r"total",
    r"overall",
    r"combined",
    r"global",
    r"consolidated",
    r"aggregated",
    r"net",
    r"gross",
]

PCT_RATE_CORE = [
    r"interest",
    r"discount",
    r"exchange",
    r"tax",
    r"dividend",
    r"inflation",
    r"deflation",
    r"yield",
    r"coupon",
    r"spread",
    r"margin",
    r"return",
    r"cap",
    r"capped",
    r"floor",
    r"collar",
    r"market",
    r"currency",
    r"treasury",
    r"variable",
    r"floating",
    r"forward",
    r"fixed",
    r"unionization",
    r"coverage",
    r"default",
    r"credit",
    r"swap",
]

PCT_RATE_SUFFIX = [
    r"rates?(?:\s+(?:cap|floor|collar))?",
    r"ratios?",
    r"yields?",
]

_MOD_PAT = rf"(?:{to_build_alternation(PCT_RATE_MODIFIERS)})"
_CORE_PAT = rf"(?:{to_build_alternation(PCT_RATE_CORE)})"
_SUFFIX_PAT = rf"(?:{to_build_alternation(PCT_RATE_SUFFIX)})"

_RATE_INNER = rf"(?:{_MOD_PAT}\s+)*(?:{_CORE_PAT}\s+)*{_SUFFIX_PAT}"

# Structure: [MOD*] CORE+ SUFFIX
# One or more core terms, must end with a suffix
PCT_RATE_RE = re.compile(
    rf"\b{_RATE_INNER}\b",  # required suffix
    re.IGNORECASE,
)

PCT = [
    r"per[- ]cent(?:age)?(?:\s+(?:rates?|points?))?",
]

_PCT_ALT = to_build_alternation(PCT)
_PCT_NUM = r"(?:-?\(?\d+(?:\.\d+)?\)?|-?\.\d+)"
_PCT_VAL_PAT = rf"{_PCT_NUM}\s*(?:%|{_PCT_ALT})"
_PCT_RANGE_PAT = rf"{_PCT_NUM}\s*%?\s*(?:-|–|—|to)\s*{_PCT_NUM}\s*(?:%|{_PCT_ALT})"
_PCT_VAL_OR_RANGE = rf"(?:{_PCT_RANGE_PAT}|{_PCT_VAL_PAT})"

_CONN_GAP = r"(?:(?:of|at|is|was|were|are|by|to|an|a|the|for|in)\s+){0,3}"

PCT_RATE_FORWARD_RE = re.compile(rf"(?<!\w){_PCT_VAL_OR_RANGE}\s+{_CONN_GAP}{_RATE_INNER}\b", re.IGNORECASE)
PCT_RATE_BACKWARD_RE = re.compile(rf"\b{_RATE_INNER}\s+{_CONN_GAP}{_PCT_VAL_OR_RANGE}(?!\w)", re.IGNORECASE)

_CHANGE_INNER = to_build_alternation(PCT_CHANGE_TERMS)
PCT_CHANGE_RE = build_regex(PCT_CHANGE_TERMS)

PCT_CHANGE_FORWARD_RE = re.compile(rf"(?<!\w){_PCT_VAL_OR_RANGE}\s+{_CONN_GAP}{_CHANGE_INNER}\b", re.IGNORECASE)
PCT_CHANGE_BACKWARD_RE = re.compile(rf"\b{_CHANGE_INNER}\s+{_CONN_GAP}{_PCT_VAL_OR_RANGE}(?!\w)", re.IGNORECASE)

PCT_RE = build_regex(PCT)
PCT_SPACE = re.compile(rf"({_PCT_NUM})\s+%", re.IGNORECASE)
PCT_RANGE = re.compile(
    rf"(?<!\w){_PCT_RANGE_PAT}(?!\w)",
    re.IGNORECASE,
)

PCT_OF_DETERMINERS = [
    r"the",
    r"a",
    r"an",
    r"each",
    r"all",
    r"any",
    r"our",
    r"its",
    r"their",
    r"his",
    r"her",
]

PCT_OF_MODIFIERS = [
    r"total",
    r"overall",
    r"combined",
    r"global",
    r"consolidated",
    r"aggregated?",
    r"net",
    r"gross",
    r"remaining",
    r"outstanding",
    r"issued",
    r"voting",
    r"common",
    r"[A-Z][a-z]+(?:ese|ish|an|ch)?",  # nationality/proper adj: Japanese, American
]

_DET = rf"(?:{to_build_alternation(PCT_OF_DETERMINERS)})\s+"
_MOD = rf"(?:[A-Za-z][\w-]*(?:'s|s')?\s+)"

_PCT_OF_CHAIN = (
    rf"(?:{_DET}){{1,4}}"  # 1-3 determiners: "of the", "of each of the"
    rf"(?:{_MOD}){{0,3}}"  # up to 3 modifier words
)

PCT_OF_RE = re.compile(
    rf"(?<!\w)({_PCT_VAL_OR_RANGE}\s+{_PCT_OF_CHAIN}[A-Za-z][\w-]+)(?!\w)",
    re.IGNORECASE,
)

PCT_NUMERIC_RE = re.compile(
    rf"(?<!\w){_PCT_VAL_PAT}(?!\w)",
    re.IGNORECASE,
)

_PCT_CHANGE_POST_ALT = to_build_alternation(PCT_CHANGE_POST_TERMS)
PCT_CHANGE_POST_RE = re.compile(
    rf"(?<!\w){_PCT_VAL_OR_RANGE}\s+(?:{_PCT_CHANGE_POST_ALT})(?!\w)",
    re.IGNORECASE,
)


def extract_spans(text: str) -> list[tuple[str, int, int, str]]:
    """
    Extract PERCENT spans from text.
    Returns (start, end, label) tuples.
    """
    if not text:
        return []

    spans: list[tuple[str, int, int, str]] = []

    def _overlaps_existing(start: int, end: int) -> bool:
        for _, s, e, _ in spans:
            if not (end <= s or start >= e):
                return True
        return False

    def _add_span(text: str, start: int, end: int, label: str) -> None:
        if _overlaps_existing(start, end):
            return
        spans.append((text, start, end, label))

    def _iter_sentences(src: str) -> list[tuple[int, int, str]]:
        out: list[tuple[int, int, str]] = []
        start = 0
        for m in SENTENCE_SPLIT_RE.finditer(src):
            end = m.end()
            chunk = src[start:end]
            if chunk.strip():
                out.append((start, end, chunk))
            start = end
        tail = src[start:]
        if tail.strip():
            out.append((start, len(src), tail))
        return out

    def _label_for_span(start: int, end: int, sentence: str) -> str:
        change_matches = list(PCT_CHANGE_RE.finditer(sentence))
        post_matches = list(PCT_CHANGE_POST_RE.finditer(sentence))
        rate_matches = list(PCT_RATE_RE.finditer(sentence))

        change_dist = closest_distance_in_segment(sentence, start, end, change_matches)
        post_dist = closest_distance_in_segment(sentence, start, end, post_matches)
        rate_dist = closest_distance_in_segment(sentence, start, end, rate_matches)

        if change_dist is not None or post_dist is not None:
            return LABELS.PCT_CHANGE.value
        if rate_dist is not None:
            return LABELS.PCT_RATE.value
        return LABELS.PCT_OTHER.value

    for sent_start, _, sentence in _iter_sentences(text):
        for m in PCT_RATE_FORWARD_RE.finditer(sentence):
            _add_span(m.group(0), sent_start + m.start(), sent_start + m.end(), LABELS.PCT_RATE.value)

        for m in PCT_RATE_BACKWARD_RE.finditer(sentence):
            _add_span(m.group(0), sent_start + m.start(), sent_start + m.end(), LABELS.PCT_RATE.value)

        for m in PCT_CHANGE_FORWARD_RE.finditer(sentence):
            _add_span(m.group(0), sent_start + m.start(), sent_start + m.end(), LABELS.PCT_CHANGE.value)

        for m in PCT_CHANGE_BACKWARD_RE.finditer(sentence):
            _add_span(m.group(0), sent_start + m.start(), sent_start + m.end(), LABELS.PCT_CHANGE.value)

        for m in PCT_CHANGE_POST_RE.finditer(sentence):
            _add_span(
                m.group(0),
                sent_start + m.start(),
                sent_start + m.end(),
                LABELS.PCT_CHANGE.value,
            )

        for m in PCT_RANGE.finditer(sentence):
            _add_span(
                m.group(0),
                sent_start + m.start(),
                sent_start + m.end(),
                _label_for_span(m.start(), m.end(), sentence),
            )

        for m in PCT_OF_RE.finditer(sentence):
            _add_span(
                m.group(1),
                sent_start + m.start(1),
                sent_start + m.end(1),
                _label_for_span(m.start(1), m.end(1), sentence),
            )

        for m in PCT_RE.finditer(sentence):
            _add_span(
                m.group(0),
                sent_start + m.start(),
                sent_start + m.end(),
                _label_for_span(m.start(), m.end(), sentence),
            )

        for m in PCT_NUMERIC_RE.finditer(sentence):
            _add_span(
                m.group(0),
                sent_start + m.start(),
                sent_start + m.end(),
                _label_for_span(m.start(), m.end(), sentence),
            )

    return spans
