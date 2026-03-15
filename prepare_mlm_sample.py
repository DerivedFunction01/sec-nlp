"""
sample_mlm.py — Extract and filter text blocks from webpage_result for MLM/DAPT.

Architecture:
  Reader thread   → DB row queue    (SQLite, sequential, I/O bound)
  Worker pool     → result queue    (CPU bound: filter + clean)
  Writer thread   → parquet chunks  (I/O bound, never blocks workers)

Intermediate parquet chunks are written every --chunk-size rows so progress
is never lost. A final merge step concatenates them into one output file.

Usage:
  python sample_mlm.py                          # defaults
  python sample_mlm.py --workers 8 --chunk-size 20000
  python sample_mlm.py --merge-only             # merge existing chunks
  python sample_mlm.py --resume                 # skip already-written chunks
"""

import argparse
import hashlib
import json
import logging
import multiprocessing as mp
import os
import random
import re
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from queue import Queue, Empty
from typing import Any, Dict, Iterator, List, Optional, Tuple

import pandas as pd
from tqdm import tqdm

# =============================================================================
# LOGGING  — routed through tqdm.write so the progress bar never breaks
# =============================================================================


class _TqdmHandler(logging.StreamHandler):
    """Emit log records via tqdm.write so they don't corrupt the progress bar."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            tqdm.write(self.format(record))
        except Exception:
            self.handleError(record)


_handler = _TqdmHandler()
_handler.setFormatter(
    logging.Formatter("%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
)
logging.basicConfig(handlers=[_handler], level=logging.INFO, force=True)
log = logging.getLogger(__name__)

# =============================================================================
# REGEX (module-level so workers don't recompile)
# =============================================================================

_WS_RE = re.compile(r"\s+")
_DASH_RUN_RE = re.compile(r"(?:-|\u2013|\u2014|=){4,}")
_UNDER_RUN_RE = re.compile(r"_ {0,1}_+")
_SPACE_AROUND_DASH = re.compile(r"\s*[-\u2013\u2014=]{2,}\s*")
_ALPHA_RE = re.compile(r"[A-Za-z]")
_DIGIT_RE = re.compile(r"\d")
_TABLE_TAG_RE = re.compile(r"^\s*<TABLE", re.IGNORECASE)
_PIPE_HEAVY_RE = re.compile(r"\|")
_PUNCT_TRAIL_RE = re.compile(r"[\s.,;:!?]+$")  # for dedupe key

# =============================================================================
# CONFIG
# =============================================================================


@dataclass(frozen=True)
class FilterConfig:
    min_chars: int
    max_chars: int
    min_alpha_ratio: float
    max_digit_ratio: float
    max_upper_ratio: float
    min_avg_line_len: int
    include_tables: bool


# =============================================================================
# TEXT HELPERS
# =============================================================================


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = _DASH_RUN_RE.sub(" — ", text)
    text = _UNDER_RUN_RE.sub(" — ", text)
    text = _SPACE_AROUND_DASH.sub(" — ", text)
    text = _WS_RE.sub(" ", text).strip()
    return text


def _alpha_ratio(text: str) -> float:
    return len(_ALPHA_RE.findall(text)) / max(len(text), 1)


def _digit_ratio(text: str) -> float:
    return len(_DIGIT_RE.findall(text)) / max(len(text), 1)


def _upper_ratio(text: str) -> float:
    letters = sum(1 for c in text if c.isalpha())
    upper = sum(1 for c in text if c.isupper())
    return upper / max(letters, 1)


def _avg_line_len(text: str) -> float:
    lines = [l for l in text.split("\n") if l.strip()]
    if not lines:
        return 999.0
    return sum(len(l) for l in lines) / len(lines)


def _dedupe_key(text: str) -> str:
    """Normalise to a stable key for cross-chunk deduplication."""
    key = text.lower()
    key = _PUNCT_TRAIL_RE.sub("", key)
    key = _WS_RE.sub(" ", key).strip()
    return key


def is_good_block(text: str, cfg: FilterConfig) -> bool:
    if not text:
        return False
    n = len(text)
    if n < cfg.min_chars or n > cfg.max_chars:
        return False
    if not cfg.include_tables:
        if _TABLE_TAG_RE.search(text):
            return False
        if _PIPE_HEAVY_RE.search(text) and _digit_ratio(text) > 0.15:
            return False
    if _alpha_ratio(text) < cfg.min_alpha_ratio:
        return False
    if _digit_ratio(text) > cfg.max_digit_ratio:
        return False
    if _upper_ratio(text) > cfg.max_upper_ratio:
        return False
    if cfg.min_avg_line_len > 0 and _avg_line_len(text) < cfg.min_avg_line_len:
        return False
    return True


# =============================================================================
# WORKER (runs in subprocess)
# =============================================================================


def _stable_hash(value: str) -> int:
    return int(hashlib.md5(value.encode()).hexdigest(), 16)


def process_batch(
    batch: List[Tuple[str, str, Optional[int], Optional[int]]],
    cfg: FilterConfig,
    per_accession: int,
    seed: int,
) -> List[Dict[str, Any]]:
    """
    Called in a worker process. Receives a list of raw DB rows,
    returns filtered + sampled blocks.
    """
    out: List[Dict[str, Any]] = []

    for accession, documents_json, cik, year in batch:
        # Parse documents
        try:
            if isinstance(documents_json, list):
                blocks = documents_json
            elif isinstance(documents_json, str):
                blocks = json.loads(documents_json)
            else:
                continue
        except (json.JSONDecodeError, TypeError):
            log.debug("Bad JSON for accession %s", accession)
            continue

        # Clean and filter
        candidates = []
        for raw in blocks:
            if not isinstance(raw, str):
                continue
            cleaned = clean_text(raw)
            if is_good_block(cleaned, cfg):
                candidates.append(cleaned)

        if not candidates:
            continue

        # Per-accession sample (deterministic by accession)
        if per_accession and len(candidates) > per_accession:
            rng = random.Random(seed ^ _stable_hash(accession or ""))
            candidates = rng.sample(candidates, per_accession)

        for text in candidates:
            out.append(
                {
                    "text": text,
                    "accession": accession,
                    "cik": cik,
                    "year": year,
                }
            )

    return out


# =============================================================================
# DB READER  (runs in its own thread)
# =============================================================================

_SENTINEL = None  # signals workers that reading is done


def db_reader_thread(
    db_path: str,
    row_queue: Queue,
    reader_batch: int,
    worker_batch: int,
    stop_event: threading.Event,
    counters: Dict,  # shared — reader increments "filings_read"
) -> None:
    """
    Reads rows from SQLite in `reader_batch` pages and pushes
    sub-batches of `worker_batch` rows onto `row_queue`.
    Runs in a daemon thread so it never blocks the main thread.
    """
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cur = conn.cursor()
    last_rowid = 0

    try:
        while not stop_event.is_set():
            cur.execute(
                """
                SELECT w.rowid, w.accession, w.documents, r.cik, r.year
                FROM   webpage_result w
                LEFT JOIN report_data r ON w.accession = r.accession
                WHERE  w.rowid > ?
                ORDER  BY w.rowid
                LIMIT  ?
                """,
                (last_rowid, reader_batch),
            )
            rows = cur.fetchall()
            if not rows:
                break

            last_rowid = rows[-1][0]
            counters["filings_read"] += len(rows)

            # Slice into worker-sized sub-batches and enqueue
            stripped = [(acc, doc, cik, yr) for _, acc, doc, cik, yr in rows]
            for i in range(0, len(stripped), worker_batch):
                sub = stripped[i : i + worker_batch]
                row_queue.put(sub)  # blocks if queue is full — natural backpressure
    finally:
        conn.close()
        row_queue.put(_SENTINEL)  # one sentinel per reader thread


# =============================================================================
# WRITER  (runs in its own thread)
# =============================================================================


def writer_thread(
    result_queue: Queue,
    chunks_dir: Path,
    chunk_size: int,
    seen_keys: set,  # shared dedupe set (only touched by writer)
    counters: Dict,  # {"written", "dropped_dupe", "chunks"}
    stop_event: threading.Event,
    num_workers: int,
) -> None:
    """
    Drains result_queue, deduplicates, and writes parquet chunks.
    Receives one _SENTINEL per worker when that worker is done.
    """
    chunks_dir.mkdir(parents=True, exist_ok=True)
    chunk_idx = _next_chunk_index(chunks_dir)
    buffer: List[Dict[str, Any]] = []
    sentinels = 0

    while sentinels < num_workers:
        try:
            item = result_queue.get(timeout=0.5)
        except Empty:
            if stop_event.is_set():
                break
            continue

        if item is _SENTINEL:
            sentinels += 1
            continue

        # Deduplicate
        for row in item:
            key = _dedupe_key(row["text"])
            if key in seen_keys:
                counters["dropped_dupe"] += 1
                continue
            seen_keys.add(key)
            buffer.append(row)
            counters["written"] += 1

        # Flush chunk
        if len(buffer) >= chunk_size:
            _write_chunk(buffer, chunks_dir, chunk_idx)
            counters["chunks"] += 1
            chunk_idx += 1
            buffer.clear()

    # Flush remainder
    if buffer:
        _write_chunk(buffer, chunks_dir, chunk_idx)
        counters["chunks"] += 1


def _next_chunk_index(chunks_dir: Path) -> int:
    existing = sorted(chunks_dir.glob("chunk_*.parquet"))
    if not existing:
        return 0
    last = existing[-1].stem  # "chunk_000042"
    return int(last.split("_")[1]) + 1


def _write_chunk(buffer: List[Dict[str, Any]], chunks_dir: Path, idx: int) -> None:
    path = chunks_dir / f"chunk_{idx:06d}.parquet"
    pd.DataFrame(buffer).to_parquet(path, index=False)
    log.info("Chunk %06d written — %d rows → %s", idx, len(buffer), path.name)


# =============================================================================
# WORKER POOL  (main thread manages)
# =============================================================================


def worker_pool(
    row_queue: Queue,
    result_queue: Queue,
    cfg: FilterConfig,
    per_accession: int,
    seed: int,
    num_workers: int,
    stop_event: threading.Event,
) -> None:
    """
    Pulls batches from row_queue, processes in a subprocess pool,
    pushes results to result_queue. Runs in the main thread.
    """
    from concurrent.futures import ProcessPoolExecutor, as_completed
    import functools

    process_fn = functools.partial(
        process_batch,
        cfg=cfg,
        per_accession=per_accession,
        seed=seed,
    )

    sentinels_seen = 0
    futures = {}
    active = True

    with ProcessPoolExecutor(max_workers=num_workers) as pool:
        while active or futures:
            # Submit new work while queue has items
            while active and len(futures) < num_workers * 4:
                try:
                    batch = row_queue.get(timeout=0.1)
                except Empty:
                    break

                if batch is _SENTINEL:
                    sentinels_seen += 1
                    active = False  # reader is done
                    break

                future = pool.submit(process_fn, batch)
                futures[future] = True

            # Collect completed futures
            done = [f for f in list(futures) if f.done()]
            for f in done:
                del futures[f]
                try:
                    rows = f.result()
                    if rows:
                        result_queue.put(rows)
                except Exception as exc:
                    log.warning("Worker error: %s", exc)

            if not done and not active and not futures:
                break

            if not done:
                time.sleep(0.01)

    # Signal writer that all workers are done
    result_queue.put(_SENTINEL)


# =============================================================================
# STATS + STRATIFICATION
# =============================================================================


def enforce_cik_cap(items: List[Dict], max_per_cik: int) -> List[Dict]:
    counts: Dict[Any, int] = {}
    result = []
    for row in items:
        cik = row.get("cik")
        if cik is not None:
            if counts.get(cik, 0) >= max_per_cik:
                continue
            counts[cik] = counts.get(cik, 0) + 1
        result.append(row)
    return result


def stratify_by_decade(items: List[Dict], target_size: int, seed: int) -> List[Dict]:
    buckets: Dict[str, List] = {}
    for row in items:
        year = row.get("year")
        decade = f"{(year // 10) * 10}s" if isinstance(year, int) else "unknown"
        buckets.setdefault(decade, []).append(row)

    log.info("Decade distribution before stratification:")
    for decade in sorted(buckets):
        log.info("  %s : %d", decade, len(buckets[decade]))

    rng = random.Random(seed)
    per_bucket = max(1, target_size // max(len(buckets), 1))
    result = []
    leftover = []

    for decade in sorted(buckets):
        rows = buckets[decade]
        if len(rows) <= per_bucket:
            result.extend(rows)
        else:
            result.extend(rng.sample(rows, per_bucket))
            leftover.extend(rows)  # oversized buckets donate to fill

    # Fill remainder
    shortage = target_size - len(result)
    if shortage > 0 and leftover:
        rng.shuffle(leftover)
        result.extend(leftover[:shortage])

    return result[:target_size]


def print_stats(raw: int, filtered: int, deduped: int, final: int) -> None:
    def pct(a, b):
        return f"{a / max(b, 1) * 100:.1f}%"

    log.info("=" * 50)
    log.info("Raw blocks read   : %10d", raw)
    log.info("After filter      : %10d  (%s)", filtered, pct(filtered, raw))
    log.info("After dedupe      : %10d  (%s)", deduped, pct(deduped, filtered))
    log.info("Final output      : %10d  (%s)", final, pct(final, deduped))
    log.info("=" * 50)


# =============================================================================
# MERGE
# =============================================================================


def merge_chunks(
    chunks_dir: Path,
    output_path: Path,
    target_size: Optional[int],
    max_per_cik: Optional[int],
    seed: int,
    debug_cols: bool,
) -> None:
    chunk_files = sorted(chunks_dir.glob("chunk_*.parquet"))
    if not chunk_files:
        log.error("No chunks found in %s", chunks_dir)
        return

    log.info("Merging %d chunks from %s ...", len(chunk_files), chunks_dir)
    dfs = [pd.read_parquet(p) for p in tqdm(chunk_files, desc="Reading chunks")]
    df = pd.concat(dfs, ignore_index=True)
    log.info("Total rows before post-processing: %d", len(df))

    rows = df.to_dict("records")

    # CIK cap
    if max_per_cik:
        before = len(rows)
        rows = enforce_cik_cap(rows, max_per_cik)
        log.info("CIK cap (%d): %d → %d", max_per_cik, before, len(rows))

    # Stratify + downsample
    if target_size:
        rows = stratify_by_decade(rows, target_size, seed)
        log.info("After stratification: %d", len(rows))

    # Drop debug cols if not wanted
    if not debug_cols:
        for r in rows:
            r.pop("accession", None)
            r.pop("cik", None)
            r.pop("year", None)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(output_path, index=False)
    log.info("Final output: %s  (%d rows)", output_path, len(rows))


# =============================================================================
# TOTAL ROW COUNT
# =============================================================================


def get_total_rows(db_path: str) -> int:
    """
    Count rows using the same LEFT JOIN the reader executes so the
    tqdm total always matches what the reader will actually yield.
    A plain COUNT(*) on webpage_result would overcount if any accessions
    have no matching report_data row and the join filters them out —
    but since we use LEFT JOIN, the real risk is the opposite: orphaned
    webpage_result rows are still returned (cik/year will be NULL).
    We count webpage_result directly, which is always correct for LEFT JOIN.
    """
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM webpage_result")
        return int(cur.fetchone()[0])
    finally:
        conn.close()


# =============================================================================
# MAIN
# =============================================================================


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract filtered text blocks for MLM training.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    # I/O
    parser.add_argument("--db", default="web_data.db")
    parser.add_argument(
        "--chunks-dir",
        default="data/mlm_chunks",
        help="Directory for intermediate parquet chunks",
    )
    parser.add_argument(
        "--output",
        default="data/training_data.parquet",
        help="Final merged output file",
    )

    # Pipeline control
    parser.add_argument(
        "--merge-only",
        action="store_true",
        help="Skip extraction, only merge existing chunks",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip chunk files that already exist (not yet implemented)",
    )

    # Parallelism
    parser.add_argument(
        "--workers",
        type=int,
        default=max(mp.cpu_count() - 2, 1),
        help="Worker processes for filtering",
    )
    parser.add_argument(
        "--reader-batch", type=int, default=2000, help="Rows per SQLite fetch page"
    )
    parser.add_argument(
        "--worker-batch",
        type=int,
        default=100,
        help="Rows per worker task (tune for CPU utilization)",
    )
    parser.add_argument(
        "--queue-depth", type=int, default=200, help="Max pending batches in row_queue"
    )

    # Chunk writing
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=25000,
        help="Rows per intermediate parquet chunk",
    )

    # Post-processing (applied at merge)
    parser.add_argument("--target-size", type=int, default=1_000_000)
    parser.add_argument(
        "--max-per-cik",
        type=int,
        default=100,
        help="Max blocks kept per CIK across all filings",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--debug-cols",
        action="store_true",
        default=True,
        help="Keep accession/cik/year columns in output",
    )
    parser.add_argument("--no-debug-cols", dest="debug_cols", action="store_false")

    # Filter parameters
    parser.add_argument("--per-accession", type=int, default=10)
    parser.add_argument("--min-chars", type=int, default=40)
    parser.add_argument("--max-chars", type=int, default=2000)
    parser.add_argument("--min-alpha-ratio", type=float, default=0.50)
    parser.add_argument("--max-digit-ratio", type=float, default=0.40)
    parser.add_argument("--max-upper-ratio", type=float, default=0.60)
    parser.add_argument("--min-avg-line-len", type=int, default=50)
    parser.add_argument("--include-tables", action="store_true")

    args = parser.parse_args()

    chunks_dir = Path(args.chunks_dir)
    output_path = Path(args.output)

    # ── Merge-only mode ───────────────────────────────────────────────────────
    if args.merge_only:
        merge_chunks(
            chunks_dir,
            output_path,
            target_size=args.target_size,
            max_per_cik=args.max_per_cik,
            seed=args.seed,
            debug_cols=args.debug_cols,
        )
        return

    # ── Extraction ────────────────────────────────────────────────────────────
    db_path = Path(args.db)
    if not db_path.exists():
        raise FileNotFoundError(f"DB not found: {db_path}")

    cfg = FilterConfig(
        min_chars=args.min_chars,
        max_chars=args.max_chars,
        min_alpha_ratio=args.min_alpha_ratio,
        max_digit_ratio=args.max_digit_ratio,
        max_upper_ratio=args.max_upper_ratio,
        min_avg_line_len=args.min_avg_line_len,
        include_tables=args.include_tables,
    )

    total_filings = get_total_rows(str(db_path))
    log.info("Filings in DB: %d", total_filings)
    log.info(
        "Workers: %d | reader_batch: %d | worker_batch: %d | chunk_size: %d",
        args.workers,
        args.reader_batch,
        args.worker_batch,
        args.chunk_size,
    )

    # Shared state
    row_queue = Queue(maxsize=args.queue_depth)
    result_queue = Queue(maxsize=args.queue_depth * 4)
    stop_event = threading.Event()
    seen_keys: set = set()
    counters = {
        "filings_read": 0,
        "written": 0,
        "dropped_dupe": 0,
        "chunks": 0,
    }

    # ── Progress bar ─────────────────────────────────────────────────────────
    pbar = tqdm(
        total=total_filings,
        unit="filing",
        desc="Extracting",
        dynamic_ncols=True,
        smoothing=0.05,
    )

    def _monitor() -> None:
        """Updates tqdm every 0.5 s from shared counters. Runs as daemon thread."""
        last = 0
        while not stop_event.is_set():
            time.sleep(0.5)
            current = counters["filings_read"]
            delta = current - last
            if delta:
                pbar.update(delta)
                last = current
            pbar.set_postfix(
                read=f"{counters['filings_read']:,}",
                kept=f"{counters['written']:,}",
                dupe=f"{counters['dropped_dupe']:,}",
                chunks=counters["chunks"],
                q_in=row_queue.qsize(),
                q_out=result_queue.qsize(),
            )
        # One final postfix update — do NOT force bar to 100%.
        # If filings_read < total_filings the gap tells you how many
        # webpage_result rows had parse/join issues and were silently skipped.
        pbar.set_postfix(
            read=f"{counters['filings_read']:,}",
            kept=f"{counters['written']:,}",
            dupe=f"{counters['dropped_dupe']:,}",
            chunks=counters["chunks"],
        )

    monitor = threading.Thread(target=_monitor, daemon=True, name="monitor")
    monitor.start()

    # ── Start reader thread ───────────────────────────────────────────────────
    reader = threading.Thread(
        target=db_reader_thread,
        args=(
            str(db_path),
            row_queue,
            args.reader_batch,
            args.worker_batch,
            stop_event,
            counters,
        ),
        daemon=True,
        name="db-reader",
    )
    reader.start()

    # ── Start writer thread ───────────────────────────────────────────────────
    writer = threading.Thread(
        target=writer_thread,
        args=(
            result_queue,
            chunks_dir,
            args.chunk_size,
            seen_keys,
            counters,
            stop_event,
            1,
        ),
        daemon=True,
        name="chunk-writer",
    )
    writer.start()

    # ── Run worker pool (blocks main thread) ─────────────────────────────────
    try:
        worker_pool(
            row_queue=row_queue,
            result_queue=result_queue,
            cfg=cfg,
            per_accession=args.per_accession,
            seed=args.seed,
            num_workers=args.workers,
            stop_event=stop_event,
        )
    except KeyboardInterrupt:
        log.info("Interrupted — flushing writer...")
        stop_event.set()
    finally:
        stop_event.set()  # ensure monitor exits
        monitor.join(timeout=2)
        pbar.close()

    reader.join(timeout=10)
    writer.join(timeout=30)

    gap = total_filings - counters["filings_read"]
    if gap > 0:
        log.warning(
            "%d filings in webpage_result were not read (bad JSON or empty documents). "
            "Check your data — these rows were skipped silently.",
            gap,
        )

    log.info(
        "Extraction complete — read=%d  kept=%d  dupe=%d  chunks=%d",
        counters["filings_read"],
        counters["written"],
        counters["dropped_dupe"],
        counters["chunks"],
    )

    # ── Auto-merge ────────────────────────────────────────────────────────────
    merge_chunks(
        chunks_dir,
        output_path,
        target_size=args.target_size,
        max_per_cik=args.max_per_cik,
        seed=args.seed,
        debug_cols=args.debug_cols,
    )

    chunk_files = sorted(chunks_dir.glob("chunk_*.parquet"))
    total_raw = (
        sum(len(pd.read_parquet(p)) for p in chunk_files)
        if chunk_files
        else counters["written"]
    )

    print_stats(
        raw=total_filings * args.per_accession,  # rough upper bound
        filtered=total_raw,
        deduped=counters["written"],
        final=args.target_size or counters["written"],
    )


if __name__ == "__main__":
    main()
