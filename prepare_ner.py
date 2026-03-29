"""
prepare_ner.py — Convert cleaned text blocks into HF-style NER training rows.

Pipeline:
  1. Read `text` rows from an input parquet file.
  2. Run `defs.labeler.process_match()` to discover labeled spans.
  3. Build a synthetic / mutated sentence from the source text.
  4. Emit Hugging Face token-classification rows:
       - words: List[str]
       - ner_tags: List[str]
  5. Write parquet chunks, then merge into a final dataset.

This script intentionally does not preserve old character offsets after mutation.
The final training example is generated directly from the synthesized text.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import logging
import multiprocessing as mp
import random
import re
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

import pandas as pd
from tqdm import tqdm

from defs.labeler import process_match
from defs.text_cleaner import clean_text, strip_angle_brackets


# =============================================================================
# LOGGING
# =============================================================================


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# =============================================================================
# REGEX / TOKENIZATION
# =============================================================================


TOKEN_RE = re.compile(r"\w+(?:[-']\w+)*|[^\w\s]", re.UNICODE)
INT_RE = re.compile(r"\b\d+\b")
YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")
MONTH_RE = (
    r"January|February|March|April|May|June|July|August|"
    r"September|October|November|December"
)
MONTH_DAY_YEAR_RE = re.compile(
    rf"\b(?P<month>{MONTH_RE})\s+(?P<day>\d{{1,2}})(?:,\s*|\s+)(?P<year>(?:19|20)\d{{2}})\b",
    re.IGNORECASE,
)

MONTH_LOOKUP = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

MONTH_NAMES = {v: k.title() for k, v in MONTH_LOOKUP.items()}


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass(frozen=True)
class SpanSlot:
    index: int
    start: int
    end: int
    label: str
    text: str
    placeholder: str


# =============================================================================
# TEXT HELPERS
# =============================================================================


def tokenize(text: str) -> List[str]:
    if not text:
        return []
    return TOKEN_RE.findall(text)


def _stable_hash(value: str) -> int:
    return int(hashlib.md5(value.encode("utf-8")).hexdigest(), 16) & 0xFFFFFFFF


def _num_to_words(n: int) -> str:
    if n < 0:
        return "minus " + _num_to_words(-n)
    if n < 20:
        return _ONES[n]
    if n < 100:
        tens, ones = divmod(n, 10)
        base = _TENS[tens]
        return base if ones == 0 else f"{base} {_ONES[ones]}"
    if n < 1000:
        hundreds, rest = divmod(n, 100)
        base = f"{_ONES[hundreds]} hundred"
        return base if rest == 0 else f"{base} {_num_to_words(rest)}"
    if n < 1_000_000:
        thousands, rest = divmod(n, 1000)
        base = f"{_num_to_words(thousands)} thousand"
        return base if rest == 0 else f"{base} {_num_to_words(rest)}"
    if n < 1_000_000_000:
        millions, rest = divmod(n, 1_000_000)
        base = f"{_num_to_words(millions)} million"
        return base if rest == 0 else f"{base} {_num_to_words(rest)}"
    if n < 1_000_000_000_000:
        billions, rest = divmod(n, 1_000_000_000)
        base = f"{_num_to_words(billions)} billion"
        return base if rest == 0 else f"{base} {_num_to_words(rest)}"
    trillions, rest = divmod(n, 1_000_000_000_000)
    base = f"{_num_to_words(trillions)} trillion"
    return base if rest == 0 else f"{base} {_num_to_words(rest)}"


_ONES = [
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
]

_TENS = [
    "",
    "",
    "twenty",
    "thirty",
    "forty",
    "fifty",
    "sixty",
    "seventy",
    "eighty",
    "ninety",
]


def _format_with_commas(value: str) -> str:
    try:
        n = int(value)
    except ValueError:
        return value
    return f"{n:,}"


def _replace_ints(text: str, style: str) -> str:
    if style == "original":
        return text

    def repl(match: re.Match[str]) -> str:
        value = match.group(0)
        if style == "commas":
            return _format_with_commas(value)
        if style == "words":
            return _num_to_words(int(value))
        if style == "random":
            choice = int(match.start() + _stable_hash(value)) % 3
            if choice == 0:
                return value
            if choice == 1:
                return _format_with_commas(value)
            return _num_to_words(int(value))
        return value

    return INT_RE.sub(repl, text)


def _mutate_time_surface(text: str, rng: random.Random, number_style: str) -> str:
    m = MONTH_DAY_YEAR_RE.search(text)
    if m:
        try:
            month = MONTH_LOOKUP[m.group("month").lower()]
            day = int(m.group("day"))
            year = int(m.group("year"))
            base = dt.date(year, month, min(day, 28))
            delta_days = rng.randint(-3650, 3650)
            shifted = base + dt.timedelta(days=delta_days)
            new_text = f"{MONTH_NAMES[shifted.month]} {shifted.day}, {shifted.year}"
            return MONTH_DAY_YEAR_RE.sub(new_text, text, count=1)
        except Exception:
            pass

    def year_repl(match: re.Match[str]) -> str:
        try:
            year = int(match.group(0))
            delta = rng.randint(-25, 25)
            return str(max(1900, min(2100, year + delta)))
        except Exception:
            return match.group(0)

    text = YEAR_RE.sub(year_repl, text)
    return _replace_ints(text, number_style)


def mutate_span_text(
    text: str,
    label: str,
    rng: random.Random,
    number_style: str,
) -> str:
    """
    Create a surface-form variant for one labeled span.

    The default behavior is conservative:
      - keep text unchanged unless numeric normalization is requested
      - use a date jitter for TIME spans when a month/day/year pattern exists
    """

    if not text:
        return text

    if label == "TIME":
        return _mutate_time_surface(text, rng, number_style)

    return _replace_ints(text, number_style)


def apply_context_map(text: str, context_rules: list[tuple[str, str]]) -> str:
    for pattern, replacement in context_rules:
        text = re.sub(pattern, replacement, text)
    return text


def load_context_map(path: Optional[str]) -> list[tuple[str, str]]:
    if not path:
        return []
    rule_path = Path(path)
    if not rule_path.exists():
        raise FileNotFoundError(f"Context map not found: {rule_path}")

    with open(rule_path) as f:
        raw = json.load(f)

    if not isinstance(raw, dict):
        raise ValueError("Context map must be a JSON object mapping regex -> replacement")

    rules: list[tuple[str, str]] = []
    for pattern, replacement in raw.items():
        rules.append((str(pattern), str(replacement)))
    return rules


# =============================================================================
# SPAN -> HF NER CONVERSION
# =============================================================================


def _build_slots(text: str, spans: list[tuple[str, int, int, str]]) -> list[SpanSlot]:
    slots: list[SpanSlot] = []
    for idx, (span_text, start, end, label) in enumerate(spans, start=1):
        slots.append(
            SpanSlot(
                index=idx,
                start=start,
                end=end,
                label=label,
                text=span_text,
                placeholder=f"__ID{idx}__",
            )
        )
    return slots


def _append_segment(
    words: list[str],
    tags: list[str],
    segment: str,
    tag: str,
) -> None:
    segment_tokens = tokenize(segment)
    if not segment_tokens:
        return
    words.extend(segment_tokens)
    tags.extend([tag] * len(segment_tokens))


def build_hf_example(
    cleaned_text: str,
    spans: list[tuple[str, int, int, str]],
    *,
    rng: random.Random,
    number_style: str,
    context_rules: list[tuple[str, str]],
) -> dict[str, Any]:
    """
    Build a single HF-style token-classification row.

    The output example is derived from the cleaned text and the current spans.
    No old offsets are preserved after the surface forms are mutated.
    """

    if not spans:
        if context_rules:
            cleaned_text = apply_context_map(cleaned_text, context_rules)
        cleaned_text = _replace_ints(cleaned_text, number_style)
        words = tokenize(cleaned_text)
        return {
            "text": cleaned_text,
            "words": words,
            "ner_tags": ["O"] * len(words),
            "template_text": cleaned_text,
            "slot_count": 0,
            "label_count": 0,
        }

    slots = _build_slots(cleaned_text, spans)
    words: list[str] = []
    tags: list[str] = []
    rendered_parts: list[str] = []

    cursor = 0
    for slot in slots:
        prefix = cleaned_text[cursor : slot.start]
        if context_rules:
            prefix = apply_context_map(prefix, context_rules)
        prefix = _replace_ints(prefix, number_style)
        _append_segment(words, tags, prefix, "O")
        rendered_parts.append(prefix)

        replacement = mutate_span_text(slot.text, slot.label, rng, number_style)
        replacement = apply_context_map(replacement, context_rules)
        replacement_tokens = tokenize(replacement)
        if replacement_tokens:
            words.extend(replacement_tokens)
            tags.append(f"B-{slot.label}")
            tags.extend([f"I-{slot.label}"] * (len(replacement_tokens) - 1))
        rendered_parts.append(replacement)

        cursor = slot.end

    suffix = cleaned_text[cursor:]
    if context_rules:
        suffix = apply_context_map(suffix, context_rules)
    suffix = _replace_ints(suffix, number_style)
    _append_segment(words, tags, suffix, "O")
    rendered_parts.append(suffix)

    final_text = "".join(rendered_parts)

    return {
        "text": final_text,
        "words": words,
        "ner_tags": tags,
        "template_text": _mask_with_placeholders(cleaned_text, slots),
        "slot_count": len(slots),
        "label_count": len({slot.label for slot in slots}),
    }


def _mask_with_placeholders(text: str, slots: list[SpanSlot]) -> str:
    if not slots:
        return text
    parts: list[str] = []
    cursor = 0
    for slot in slots:
        parts.append(text[cursor : slot.start])
        parts.append(slot.placeholder)
        cursor = slot.end
    parts.append(text[cursor:])
    return "".join(parts)


# =============================================================================
# WORKER FUNCTIONS
# =============================================================================


def process_row(
    row: dict[str, Any],
    *,
    seed: int,
    number_style: str,
    max_emp_count: Optional[int],
    context_rules: list[tuple[str, str]],
    require_entity: bool,
) -> Optional[dict[str, Any]]:
    raw_text = row.get("text", "")
    if not isinstance(raw_text, str) or not raw_text.strip():
        return None

    cik = row.get("cik")
    cleaned_text = clean_text(raw_text, cik)
    stripped_text, _ = strip_angle_brackets(cleaned_text)
    spans = process_match(raw_text, cik=cik, max_emp_count=max_emp_count)

    if require_entity and not spans:
        return None

    row_seed = seed ^ _stable_hash(cleaned_text[:512]) ^ _stable_hash(str(row.get("accession", "")))
    rng = random.Random(row_seed)
    example = build_hf_example(
        stripped_text,
        spans,
        rng=rng,
        number_style=number_style,
        context_rules=context_rules,
    )

    example.update(
        {
            "accession": row.get("accession"),
            "cik": row.get("cik"),
            "year": row.get("year"),
        }
    )
    return example


def process_batch(
    rows: list[dict[str, Any]],
    *,
    seed: int,
    number_style: str,
    max_emp_count: Optional[int],
    context_rules: list[tuple[str, str]],
    require_entity: bool,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        example = process_row(
            row,
            seed=seed,
            number_style=number_style,
            max_emp_count=max_emp_count,
            context_rules=context_rules,
            require_entity=require_entity,
        )
        if example is not None:
            out.append(example)
    return out


# =============================================================================
# CHUNK WRITER / MERGE
# =============================================================================


def _chunk_paths(chunks_dir: Path) -> list[Path]:
    return sorted(chunks_dir.glob("chunk_*.parquet"))


def _next_chunk_index(chunks_dir: Path) -> int:
    existing = _chunk_paths(chunks_dir)
    if not existing:
        return 0
    return int(existing[-1].stem.split("_")[1]) + 1


def _write_chunk(buffer: list[dict[str, Any]], chunks_dir: Path, idx: int) -> None:
    chunks_dir.mkdir(parents=True, exist_ok=True)
    path = chunks_dir / f"chunk_{idx:06d}.parquet"
    pd.DataFrame(buffer).to_parquet(path, index=False)
    log.info("Chunk %06d written: %d rows -> %s", idx, len(buffer), path.name)


def merge_chunks(chunks_dir: Path, output_path: Path, debug_cols: bool) -> None:
    chunk_files = _chunk_paths(chunks_dir)
    if not chunk_files:
        raise FileNotFoundError(f"No chunk parquet files found in {chunks_dir}")

    log.info("Merging %d chunks from %s", len(chunk_files), chunks_dir)
    dfs = [pd.read_parquet(p) for p in tqdm(chunk_files, desc="Reading chunks")]
    df = pd.concat(dfs, ignore_index=True)

    if not debug_cols:
        drop_cols = [c for c in ("accession", "cik", "year", "template_text", "slot_count", "label_count") if c in df.columns]
        if drop_cols:
            df = df.drop(columns=drop_cols)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)
    log.info("Merged output written to %s (%d rows)", output_path, len(df))


def print_stats(raw: int, kept: int, final: int) -> None:
    def pct(a: int, b: int) -> str:
        return f"{(a / max(b, 1)) * 100:.1f}%"

    log.info("=" * 50)
    log.info("Raw rows          : %10d", raw)
    log.info("Kept examples      : %10d  (%s)", kept, pct(kept, raw))
    log.info("Final output       : %10d  (%s)", final, pct(final, kept))
    log.info("=" * 50)


# =============================================================================
# MAIN
# =============================================================================


def _batched(items: list[dict[str, Any]], batch_size: int) -> Iterator[list[dict[str, Any]]]:
    for i in range(0, len(items), batch_size):
        yield items[i : i + batch_size]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate HF token-classification parquet from cleaned text blocks.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument("--input", default="data/training_data.parquet")
    parser.add_argument("--output", default="data/ner_training_data.parquet")
    parser.add_argument("--chunks-dir", default="data/ner_chunks")
    parser.add_argument("--labels-output", default="data/ner_labels.json")

    parser.add_argument("--merge-only", action="store_true")
    parser.add_argument("--debug-cols", action="store_true", default=True)
    parser.add_argument("--no-debug-cols", dest="debug_cols", action="store_false")

    parser.add_argument("--workers", type=int, default=max(mp.cpu_count() - 2, 1))
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--chunk-size", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=42)

    parser.add_argument("--max-emp-count", type=int, default=None)
    parser.add_argument(
        "--number-style",
        choices=("original", "commas", "words", "random"),
        default="random",
        help="How numeric substrings are rendered inside span and context text.",
    )
    parser.add_argument(
        "--context-map",
        default=None,
        help="Optional JSON file mapping regex patterns to replacement strings for context text.",
    )
    parser.add_argument(
        "--require-entity",
        action="store_true",
        default=False,
        help="Drop examples with no labeled spans.",
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    chunks_dir = Path(args.chunks_dir)

    if args.merge_only:
        merge_chunks(chunks_dir, output_path, debug_cols=args.debug_cols)
        return

    if not input_path.exists():
        raise FileNotFoundError(f"Input parquet not found: {input_path}")

    context_rules = load_context_map(args.context_map)

    df = pd.read_parquet(input_path)
    if "text" not in df.columns:
        raise ValueError(f"{input_path} must contain a 'text' column")

    rows = df.to_dict("records")
    raw_rows = len(rows)
    log.info("Loaded %d rows from %s", raw_rows, input_path)
    log.info(
        "Workers: %d | batch_size: %d | chunk_size: %d | number_style: %s",
        args.workers,
        args.batch_size,
        args.chunk_size,
        args.number_style,
    )

    chunks_dir.mkdir(parents=True, exist_ok=True)
    chunk_idx = _next_chunk_index(chunks_dir)
    buffer: list[dict[str, Any]] = []
    kept = 0

    if args.workers <= 1:
        iterable: Iterable[list[dict[str, Any]]] = _batched(rows, args.batch_size)
        for batch in tqdm(iterable, total=(len(rows) + args.batch_size - 1) // args.batch_size, desc="Preparing"):
            batch_out = process_batch(
                batch,
                seed=args.seed,
                number_style=args.number_style,
                max_emp_count=args.max_emp_count,
                context_rules=context_rules,
                require_entity=args.require_entity,
            )
            for item in batch_out:
                buffer.append(item)
                kept += 1
                if len(buffer) >= args.chunk_size:
                    _write_chunk(buffer, chunks_dir, chunk_idx)
                    chunk_idx += 1
                    buffer.clear()
    else:
        batches = list(_batched(rows, args.batch_size))
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = {
                pool.submit(
                    process_batch,
                    batch,
                    seed=args.seed,
                    number_style=args.number_style,
                    max_emp_count=args.max_emp_count,
                    context_rules=context_rules,
                    require_entity=args.require_entity,
                ): idx
                for idx, batch in enumerate(batches)
            }

            for future in tqdm(as_completed(futures), total=len(futures), desc="Preparing"):
                batch_out = future.result()
                for item in batch_out:
                    buffer.append(item)
                    kept += 1
                    if len(buffer) >= args.chunk_size:
                        _write_chunk(buffer, chunks_dir, chunk_idx)
                        chunk_idx += 1
                        buffer.clear()

    if buffer:
        _write_chunk(buffer, chunks_dir, chunk_idx)

    chunk_files = _chunk_paths(chunks_dir)
    final_rows = sum(len(pd.read_parquet(p)) for p in chunk_files) if chunk_files else kept
    merge_chunks(chunks_dir, output_path, debug_cols=args.debug_cols)

    labels: set[str] = {"O"}
    if chunk_files:
        for p in chunk_files:
            df_chunk = pd.read_parquet(p, columns=["ner_tags"])
            for tags in df_chunk["ner_tags"]:
                if isinstance(tags, list):
                    labels.update(tags)
                elif isinstance(tags, str):
                    try:
                        labels.update(json.loads(tags))
                    except Exception:
                        pass

    labels_path = Path(args.labels_output)
    labels_path.parent.mkdir(parents=True, exist_ok=True)
    with open(labels_path, "w") as f:
        json.dump(sorted(labels), f, indent=2)
    log.info("Label list written to %s", labels_path)

    print_stats(raw=raw_rows, kept=kept, final=final_rows)


if __name__ == "__main__":
    main()
