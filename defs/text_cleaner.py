import re
import difflib
from pathlib import Path
from typing import Optional, Union
from defs.regex_lib import CONSEC_DIGIT_RE, build_alternation, build_regex
import pandas as pd
COMPANY_TOKEN = "the Company"

SPACE_RE = re.compile(r"\s+")
PUNCT_SPACE_RE = re.compile(r"\s+([,\.;\:\!\?])")
DOUBLE_PUNCT_RE = re.compile(r"([,\.;\:\!\?])\1+")
MISSING_SPACE_RE = re.compile(r"(?:(?<!\b[A-Z])\.|[,;\:\!\?])(?=[a-zA-Z])")
HANGING_APOSTROPHE_RE = re.compile(r"\s+'(s|re|ve|t|m|ll|d)\b", re.IGNORECASE)


def clean_spaces_and_punctuation(text: str) -> str:
    """
    Normalizes whitespace and cleans up punctuation.
    """
    if not text:
        return ""
    text = SPACE_RE.sub(" ", text).strip()
    text = PUNCT_SPACE_RE.sub(r"\1", text)
    text = DOUBLE_PUNCT_RE.sub(r"\1", text)
    text = MISSING_SPACE_RE.sub(r"\g<0> ", text)
    text = HANGING_APOSTROPHE_RE.sub(r"'\1", text)
    return text

class TextCleaner:
    """
    Minimal text cleaning stripping misc content
    """
    # Links https or www
    cleanup_patterns = [
        (re.compile(r"(?:\b\d{1,3}\s*)?<PAGE>(?:\s*\d{1,3}\b)?", re.IGNORECASE), r""),
        (re.compile(r"(?<!\d)-\s*\d{1,3}\s*-(?!\d)", re.IGNORECASE), r""),
        (
            re.compile(
                r"(?:"
                r'https?://[^\s<>"\'()]+(?<![.,;:!?])'  # standard http/https URLs
                r'|www\.[^\s<>"\'()]+(?<![.,;:!?])'  # www. without scheme
                r"|[a-zA-Z0-9\-]+\."  # bare domain
                r"(?:com|org|net|io|co|uk|edu|gov|me|dev|ai|app)"
                r'(?:/[^\s<>"\'()]*[^\s<>"\'().,;:!?])?'
                r")",
                re.IGNORECASE,
            ),
            r"",
        ),
        # toc style . . . . . 5 (at least 4 dots (optional spaces between dots) then a number)
        (re.compile(r"(?:\.\s*){4,}\d{1,3}", re.IGNORECASE), r""),
    ]
    def __init__(self):
        pass

    def clean(self, text: str) -> str:
        if not text:
            return ""
        for pattern, replacement in self.cleanup_patterns:
            text = pattern.sub(replacement, text)
        return clean_spaces_and_punctuation(text)

class NumberNormalizer:
    """
    Minimal numeric normalization without stripping content.
    Focuses on converting word-number phrases and normalizing numeric formats.
    """
    def __init__(self, numeric_firm_cleaner: Optional["NumericFirmCleaner"] = None):
        self.numeric_firm_cleaner = numeric_firm_cleaner or NumericFirmCleaner()

    num_words = {
        "zero": 0,
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
        "eleven": 11,
        "twelve": 12,
        "thirteen": 13,
        "fourteen": 14,
        "fifteen": 15,
        "sixteen": 16,
        "seventeen": 17,
        "eighteen": 18,
        "nineteen": 19,
        "twenty": 20,
        "thirty": 30,
        "forty": 40,
        "fifty": 50,
        "sixty": 60,
        "seventy": 70,
        "eighty": 80,
        "ninety": 90,
    }
    multipliers = {
        "dozen": 12,
        "hundred": 100,
        "thousand": 1_000,
        "million": 1_000_000,
        "billion": 1_000_000_000,
        "trillion": 1_000_000_000_000,
    }
    fractions = {
        "half": 0.5,
        "halves": 0.5,
        "quarter": 0.25,
        "quarters": 0.25,
        "third": 1 / 3,
        "thirds": 1 / 3,
        "fourth": 0.25,
        "fourths": 0.25,
        "fifth": 0.2,
        "fifths": 0.2,
        "sixth": 1 / 6,
        "sixths": 1 / 6,
        "seventh": 1 / 7,
        "sevenths": 1 / 7,
        "eighth": 1 / 8,
        "eighths": 1 / 8,
        "ninth": 1 / 9,
        "ninths": 1 / 9,
        "tenth": 0.1,
        "tenths": 0.1,
    }

    _all_words = (
        list(num_words.keys()) + list(multipliers.keys()) + list(fractions.keys())
    )
    _word_pattern = build_alternation([re.escape(w) for w in _all_words])
    number_phrase_pattern = re.compile(
        rf"\b{_word_pattern}(?:[\s-]+{_word_pattern})*\b", re.IGNORECASE
    )
    qualitative_patterns = [
        (
            re.compile(
                rf"\ba\s+few\s+(?={build_alternation(list(multipliers.keys()))})",
                re.IGNORECASE,
            ),
            "three ",
        ),
        (
            re.compile(
                rf"\bhalf\s+(?:of\s+)?(?:a\s+)?(?={build_alternation(list(multipliers.keys()))})",
                re.IGNORECASE,
            ),
            "0.5 ",
        ),
        (
            re.compile(
                rf"\ba\+quarter\s+(?:of\s+)?(?:a\s+)?(?={build_alternation(list(multipliers.keys()))})",
                re.IGNORECASE,
            ),
            "0.25 ",
        ),
        (
            re.compile(
                rf"\bthree\+quarters\s+(?:of\s+)?(?:a\s+)?(?={build_alternation(list(multipliers.keys()))})",
                re.IGNORECASE,
            ),
            "0.75 ",
        ),
        (
            re.compile(
                rf"\ba\s+(?={build_alternation(list(multipliers.keys()))}|(?:quarter|third|fifth|sixth)\s+of)",
                re.IGNORECASE,
            ),
            "one ",
        ),
    ]
    comma_pattern = re.compile(r"(?<=\d),(?=\d{3})")
    parenthetical_duplicate_number_pattern = re.compile(
        r"\b(?P<left>\d+(?:\.\d+)?)\s*\(\s*(?P<right>\d+(?:\.\d+)?)\s*\)"
    )
    scale_map = {
        "dozen": 12,
        "hundred": 100,
        "thousand": 1_000,
        "million": 1_000_000,
        "billion": 1_000_000_000,
        "trillion": 1_000_000_000_000,
    }
    scale_pattern = re.compile(
        rf"\b(\d+(?:\.\d+)?)\s+({'|'.join(scale_map.keys())})\b", re.IGNORECASE
    )
    _fraction_words = "|".join(
        list(fractions.keys())
        + [w[:-3] for w in fractions.keys() if w.endswith("ths")]
    )
    _num_words_str = "|".join(num_words.keys())
    hyphenated_fraction_pattern = re.compile(
        rf"\b({_num_words_str})-({_fraction_words}s?)\b", re.IGNORECASE
    )
    fraction_qualifiers = {
        "approx",
        "approx.",
        "approximately",
        "roughly",
        "nearly",
        "about",
        "around",
        "almost",
    }
    percent_pattern = re.compile(r"\bper[- ]?cent\b", re.IGNORECASE)
    _pct_num = r"(?:-?\(?\d+(?:\.\d+)?\)?|-?\.\d+)"
    percent_space_pattern = re.compile(rf"({_pct_num})\s+%", re.IGNORECASE)
    percent_range_pattern = re.compile(
        rf"(?<!\w)({_pct_num})\s*%?\s*(?:-|–|—|to)\s*({_pct_num})\s*%",
        re.IGNORECASE,
    )
    leading_decimal_pattern = re.compile(r"(?:(?<=^)|(?<=\s))\.(\d+)\b")

    # zip_code_pattern = re.compile(r"\b\d{5}(?:-\d{4})?\b")
    def _convert_hyphenated_fraction(self, match):
        num_word = match.group(1).lower()
        frac_word = match.group(2).lower()
        if num_word not in self.num_words:
            return match.group(0)
        numerator = self.num_words[num_word]

        if frac_word not in self.fractions:
            frac_base = frac_word.rstrip("s")
            if frac_base not in self.fractions:
                return match.group(0)
            denominator = self.fractions[frac_base]
        else:
            denominator = self.fractions[frac_word]

        result = numerator * denominator
        return f"{result * 100:g}%"

    def _scale_replacer(self, match):
        try:
            number = float(match.group(1))
            multiplier = self.scale_map.get(match.group(2).lower(), 1)
            value = number * multiplier
            if value.is_integer():
                return f"{int(value)}"
            return f"{value}"
        except ValueError:
            return match.group(0)

    def _parse_number_phrase(self, match):
        text = match.group(0)
        clean_text = text.lower().replace("-", " ")
        words = clean_text.split()

        if all(w in self.multipliers for w in words):
            return text

        has_number = any(w in self.num_words for w in words)
        has_qualifier = any(w in self.fraction_qualifiers for w in words)
        has_fraction = any(w in self.fractions for w in words)
        if has_fraction and not has_number and not has_qualifier:
            is_safe = True
            for w in words:
                if w not in ["half"]:
                    is_safe = False
                    break
            if not is_safe:
                return text

        if len(words) >= 2:
            for i in range(len(words) - 1):
                word = words[i]
                next_word = words[i + 1]
                if word in self.num_words:
                    if next_word.endswith("ths"):
                        base = next_word[:-3]
                        if base in self.fractions:
                            num = self.num_words[word]
                            frac = self.fractions[base]
                            result = num * frac
                            return f"{result * 100:g}%"
                    elif next_word == "halves":
                        num = self.num_words[word]
                        result = num * 0.5
                        return f"{result * 100:g}%"

        total_value = 0
        current_chunk = 0
        is_fraction = False
        fraction_value = 0.0

        for word in words:
            if word in self.num_words:
                current_chunk += self.num_words[word]
            elif word in self.multipliers:
                mult = self.multipliers[word]
                if mult < 1000:
                    current_chunk = (current_chunk if current_chunk else 1) * mult
                else:
                    total_value += (current_chunk if current_chunk else 1) * mult
                    current_chunk = 0
            elif word in self.fractions:
                if current_chunk > 0:
                    fraction_value += current_chunk * self.fractions[word]
                    current_chunk = 0
                    is_fraction = True
                elif word in ["half"]:
                    fraction_value += self.fractions[word]
                    is_fraction = True

        if is_fraction:
            final_val = total_value + fraction_value
            if final_val == 0:
                return text
            return f"{final_val * 100:g}%"

        total_value += current_chunk
        if total_value == 0 and "zero" not in clean_text:
            return text
        return str(total_value)

    def _collapse_parenthetical_duplicate_numbers(self, text: str) -> str:
        def repl(match: re.Match) -> str:
            left = match.group("left")
            right = match.group("right")
            try:
                if float(left) == float(right):
                    return left
            except ValueError:
                return match.group(0)
            return match.group(0)

        return self.parenthetical_duplicate_number_pattern.sub(repl, text)

    def normalize(self, text: str) -> str:
        if not text:
            return ""
        text = CONSEC_DIGIT_RE.sub(r"<\1>", text)
        
        # Preserve numeric firm names before any number conversion
        numeric_firm_map = {}
        if self.numeric_firm_cleaner:
            text, numeric_firm_map = self.numeric_firm_cleaner.mask_numeric_names(text)

        # Hyphenated fractions like "three-fourths"
        text = self.hyphenated_fraction_pattern.sub(
            self._convert_hyphenated_fraction, text
        )

        # Qualitative replacements
        for pattern, replacement in self.qualitative_patterns:
            text = pattern.sub(replacement, text)

        # Word-number phrases
        text = self.number_phrase_pattern.sub(self._parse_number_phrase, text)

        # Commas in numbers
        text = self.comma_pattern.sub("", text)

        # Scale expansion (e.g., 2 million -> 2000000)
        text = self.scale_pattern.sub(self._scale_replacer, text)

        # Collapse duplicates like "15 (15)"
        text = self._collapse_parenthetical_duplicate_numbers(text)

        # Leading decimals like ".25" -> "0.25"
        text = self.leading_decimal_pattern.sub(r"0.\1", text)

        # Percent normalization
        text = self.percent_pattern.sub("%", text)
        text = self.percent_range_pattern.sub(r"\1% to \2%", text)
        text = self.percent_space_pattern.sub(r"\1%", text)

        if self.numeric_firm_cleaner:
            text = self.numeric_firm_cleaner.unmask_numeric_names(text, numeric_firm_map)

        return clean_spaces_and_punctuation(text)

class CompanyNameReplacer:
    """
    Replace the current company's name with COMPANY_TOKEN. Supports lookup by CIK.
    """

    name_suffixes = [
        r"inc\.?",
        r"corp\.?",
        r"corporation",
        r"l\.?l\.?c\.?",
        r"co\.?",
        r"company",
        r"ltd\.?",
        r"limited",
        r"p\.?l\.?c\.?",
        r"s\.?a\.?",
        r"group",
        r"holdings?",
        r"trust",
        r"assoc\.?",
        r"association",
    ]

    num_words = NumberNormalizer.num_words

    def __init__(self, cik_path: str = "data/cik_names.parquet"):
        self.cik_path = Path(cik_path)
        self._cik_to_name: Optional[dict[str, str]] = None
        self.name_suffix_pattern = re.compile(
            r"\s+" + build_alternation(self.name_suffixes) + r"\.?$", re.IGNORECASE
        )

    def _load_cik_names(self) -> None:
        if self._cik_to_name is not None:
            return
        if not self.cik_path.exists():
            self._cik_to_name = {}
            return
        df = pd.read_parquet(self.cik_path)

        if "cik" not in df.columns or "name" not in df.columns:
            self._cik_to_name = {}
            return

        mapping = {}
        for _, row in df.iterrows():
            cik = str(row["cik"]).strip()
            name = str(row["name"]).strip()
            if cik and name:
                mapping[cik] = name
        self._cik_to_name = mapping

    def normalize_company_name(self, name: str) -> str:
        if not name:
            return ""
        name = name.strip()
        prev_name = None
        while name != prev_name:
            prev_name = name
            candidate = self.name_suffix_pattern.sub("", name).strip()

            tokens = candidate.split()
            if len(tokens) == 1:
                token = tokens[0].lower()
                if token.isdigit() or token in self.num_words:
                    return name

            name = candidate
        return name

    def _resolve_company_name(self, company_name: Optional[str], cik: Optional[Union[str, int]]) -> str:
        if company_name:
            return company_name
        if not cik:
            return ""
        self._load_cik_names()
        if not self._cik_to_name:
            return ""
        return self._cik_to_name.get(str(cik).strip(), "")

    def replace(self, text: str, company_name: Optional[str] = None, cik: Optional[Union[str, int]] = None) -> str:
        if not text:
            return ""

        name = self._resolve_company_name(company_name, cik)
        if not name:
            return text

        core_name = self.normalize_company_name(name)
        if len(core_name) < 3:
            return text

        escaped_name = re.escape(core_name)
        suffix_regex = r"(?:\s+(?:" + "|".join(self.name_suffixes) + r")\.?)*"
        company_regex = re.compile(
            rf"\b{escaped_name}{suffix_regex}(?:\b|(?<=\.))", re.IGNORECASE
        )
        return company_regex.sub(COMPANY_TOKEN, text)


class NumericFirmCleaner:
    def __init__(self):
        self.candidate_pattern = re.compile(
            r"\b[A-Z1-9][\w\-\']*(?:\s+(?:&|and|of|the|[A-Z][\w\-\']+))*\b"
        )
        self.numeric_firms_regex = None
        self._numeric_firm_list = []
        self._load_numeric_firms()

    def _load_numeric_firms(self) -> None:
        file_path = Path("data/numeric_firm_names.csv")
        if not file_path.exists():
            return

        try:  
            df = pd.read_csv(file_path, encoding="utf-8")
        except Exception:
            return

        if "core_name" not in df.columns:
            return

        # Clean and filter
        df = df.dropna(subset=["core_name"])
        df["core_name"] = df["core_name"].astype(str).str.strip()
        df = df[df["core_name"].str.len() >= 3]

        numeric_names = set()
        numeric_list = []

        for name in df["core_name"]:
            parts = str(name).strip().split()
            prefixes = {name}
            if len(parts) > 2:
                for i in range(2, len(parts)):
                    prefix = " ".join(parts[:i])
                    if prefix.lower().endswith((" of", " and", " &", " for")):
                        continue
                    prefixes.add(prefix)

            for p in prefixes:
                numeric_names.add(p)
                numeric_list.append(p)

        self._numeric_firm_list = numeric_list
        if numeric_names:
            sorted_names = sorted(numeric_names, key=len, reverse=True)
            self.numeric_firms_regex = re.compile(
                r"\b(?:" + "|".join(re.escape(n) for n in sorted_names) + r")\b",
                re.IGNORECASE,
            )

    def clean_numeric_names(self, text: str) -> str:
        if not text:
            return ""

        if self.numeric_firms_regex:
            text = self.numeric_firms_regex.sub(
                lambda m: (
                    COMPANY_TOKEN
                    if (m.group(0)[0].isupper() or m.group(0)[0].isdigit())
                    else m.group(0)
                ),
                text,
            )

        if self._numeric_firm_list:
            matches = list(self.candidate_pattern.finditer(text))
            if matches:
                candidates = pd.Series([m.group(0) for m in matches])
                spans = [m.span() for m in matches]

                firm_series = pd.Series(self._numeric_firm_list)

                replacements = []
                for i, candidate in enumerate(candidates):
                    if len(candidate) < 2:
                        continue
                    cand_lower = candidate.lower()
                    ratios = firm_series.apply(
                        lambda f: difflib.SequenceMatcher(
                            None, cand_lower, f.lower()
                        ).ratio()
                    )
                    if ratios.max() >= 0.85:
                        replacements.append(spans[i])

                for start, end in sorted(replacements, reverse=True):
                    text = text[:start] + COMPANY_TOKEN + text[end:]

        return text

    def mask_numeric_names(self, text: str) -> tuple[str, dict[str, str]]:
        if not text:
            return "", {}

        mapping = {}
        counter = 0

        def repl_exact(m):
            nonlocal counter
            val = m.group(0)
            if val[0].isupper() or val[0].isdigit():
                placeholder = f"__NUMERIC_FIRM_{counter}__"
                mapping[placeholder] = val
                counter += 1
                return placeholder
            return val

        if self.numeric_firms_regex:
            text = self.numeric_firms_regex.sub(repl_exact, text)

        if self._numeric_firm_list:
            matches = list(self.candidate_pattern.finditer(text))
            if matches:
                candidates = pd.Series([m.group(0) for m in matches])
                spans = [m.span() for m in matches]

                firm_series = pd.Series(self._numeric_firm_list)

                replacements = []
                for i, candidate in enumerate(candidates):
                    if len(candidate) < 2:
                        continue
                    cand_lower = candidate.lower()
                    ratios = firm_series.apply(
                        lambda f: difflib.SequenceMatcher(
                            None, cand_lower, f.lower()
                        ).ratio()
                    )
                    if ratios.max() >= 0.85:
                        replacements.append((spans[i], candidate))

                for (start, end), candidate in sorted(
                    replacements, key=lambda x: x[0][0], reverse=True
                ):
                    placeholder = f"__NUMERIC_FIRM_{counter}__"
                    mapping[placeholder] = candidate
                    counter += 1
                    text = text[:start] + placeholder + text[end:]

        return text, mapping

    def unmask_numeric_names(self, text: str, mapping: dict[str, str]) -> str:
        if not text or not mapping:
            return text
        for placeholder, original in mapping.items():
            text = text.replace(placeholder, original)
        return text

_TEXT_CLEANER = TextCleaner()
_NUM_NORMALIZER = NumberNormalizer()
_COMPANY_NAME_REPLACER = CompanyNameReplacer()
_NUMERIC_FIRM_CLEANER = NumericFirmCleaner()


def clean_text(text: str, cik: Optional[Union[str, int]] = None) -> str:
    text = _TEXT_CLEANER.clean(text)
    text = _NUM_NORMALIZER.normalize(text)
    return text.strip()


def strip_angle_brackets(text: str) -> tuple[str, list[int]]:
    """
    Remove < and > from text, returning the stripped text and
    a position map: stripped_pos -> original_pos.
    """
    stripped_chars: list[str] = []
    pos_map: list[int] = []  # index i -> original index for stripped[i]

    for orig_i, ch in enumerate(text):
        if ch in "<>":
            continue
        stripped_chars.append(ch)
        pos_map.append(orig_i)

    return "".join(stripped_chars), pos_map


def remap_span(pos_map: list[int], start: int, end: int) -> tuple[int, int]:
    """Map a [start, end) span in stripped text back to original coordinates."""
    orig_start = pos_map[start]
    orig_end = pos_map[end - 1] + 1
    return orig_start, orig_end
