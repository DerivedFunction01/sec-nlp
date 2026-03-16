from dataclasses import dataclass, field
from re import Pattern
import re
from typing import List, Optional


@dataclass
class Span:
    start: int
    end: int
    label: str
    text: str


class SpanCollector:
    """
    Owns a piece of text and incrementally extracts spans from it.
    Each consume_* call masks already-matched regions so later patterns
    don't double-match.
    """

    def __init__(self, text: str):
        self.original: str = text
        self._masked: str = text
        self.spans: List[Span] = []

    def consume(self, pattern: Pattern[str], label: str) -> "SpanCollector":
        """Find matches in the currently unmasked text, record spans, mask them."""
        new_spans: List[Span] = []
        for m in pattern.finditer(self._masked):
            new_spans.append(Span(m.start(), m.end(), label, m.group(0)))

        if new_spans:
            self.spans.extend(new_spans)
            chars = list(self._masked)
            for s in new_spans:
                for i in range(s.start, s.end):
                    chars[i] = " "
            self._masked = "".join(chars)

        return self  # allows chaining

    def sorted_spans(self) -> List[Span]:
        """Return spans sorted by start position."""
        return sorted(self.spans, by=lambda s: s.start)

    def to_bio(self) -> List[tuple[str, str]]:
        """
        Convert to BIO token-label pairs using whitespace tokenization.
        Tokens not covered by any span get label 'O'.
        """
        tokens = []
        for m in re.finditer(r"\S+", self.original):
            tok_start, tok_end = m.start(), m.end()
            label = "O"
            for span in self.spans:
                if span.start <= tok_start and tok_end <= span.end:
                    label = span.label
                    break
            tokens.append((m.group(0), label))
        return tokens
