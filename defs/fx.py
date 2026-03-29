from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import Iterable, Optional

from defs.regex_lib import build_alternation
from defs.region_regex import MAJOR_CURRENCIES, NATION_BY_CODE, NATION_TO_CURRENCY_CODES


_REGEX_META_RE = re.compile(r"[\^\$\*\+\?\{\}\[\]\\\|\(\)]")
_WORD_RE = re.compile(r"^\w[\w\s.'/-]*\w$|^\w$")
_ADJ_SUFFIXES = ("an", "ian", "ean", "ese", "ic", "ish", "ch", "ese", "ian")
_NUM = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+"
_SCALE_WORD = r"(?:thousand|million|billion|trillion|mm|m|k|b|t)"
_AMOUNT_AFTER_CURRENCY_RE = re.compile(
    rf"^\s*(?P<amount>\(?\s*(?:{_NUM})(?:\s*{_SCALE_WORD})?\s*\)?)(?P<trailing>\s*)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class FXSurface:
    kind: str
    code: str
    surface: str
    nation_code: str | None = None
    currency_code: str | None = None


@dataclass(frozen=True)
class FXBundle:
    nation_code: str
    nation_name: str
    country_terms: tuple[str, ...]
    adjective_terms: tuple[str, ...]
    city_terms: tuple[str, ...]
    currency_code: str | None
    currency_terms: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class FXHit:
    start: int
    end: int
    surface: str
    kind: str
    nation_code: str | None
    currency_code: str | None


def _is_plain_surface(term: str) -> bool:
    return not bool(_REGEX_META_RE.search(term))


def _is_word_surface(term: str) -> bool:
    return bool(_WORD_RE.match(term)) and _is_plain_surface(term)


def _titlecase_surface(surface: str) -> str:
    parts = re.split(r"(\s+|-)", surface)
    titled: list[str] = []
    for part in parts:
        if part == "" or part.isspace() or part == "-":
            titled.append(part)
            continue
        if part.isupper():
            titled.append(part)
        elif part.lower() in {"us", "usa"}:
            titled.append(part.upper())
        else:
            titled.append(part[:1].upper() + part[1:].lower())
    return "".join(titled)


def _unique_preserve_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _looks_like_adjective(term: str) -> bool:
    lower = term.lower().strip()
    if not lower or " " in lower:
        return False
    return lower.endswith(_ADJ_SUFFIXES)


def _flat_location_terms(nation) -> list[str]:
    terms: list[str] = []

    def visit_location(location) -> None:
        if location.name:
            terms.append(location.name)
        for phrase in getattr(location, "phrases", []):
            if phrase:
                terms.append(phrase)
        for city in getattr(location, "cities", []):
            visit_location(city)

    for loc in getattr(nation, "locations", []):
        visit_location(loc)

    return _unique_preserve_order(
        _titlecase_surface(term) for term in terms if term and _is_plain_surface(term)
    )


def _country_terms(nation) -> list[str]:
    terms = [nation.name]
    for phrase in getattr(nation, "phrases", []):
        if not phrase or phrase == nation.name or not _is_plain_surface(phrase):
            continue
        if _looks_like_adjective(phrase):
            continue
        terms.append(phrase)
    return _unique_preserve_order(_titlecase_surface(term) for term in terms)


def _adjective_terms(nation, currency_code: str | None = None) -> list[str]:
    terms: list[str] = []
    for phrase in getattr(nation, "phrases", []):
        if not phrase or phrase == nation.name or not _is_plain_surface(phrase):
            continue
        if _looks_like_adjective(phrase):
            terms.append(phrase)
    if currency_code:
        currency_adj = MAJOR_CURRENCIES.get(currency_code, {}).get("adj")
        if currency_adj and _is_plain_surface(str(currency_adj)):
            terms.append(str(currency_adj))
    if not terms:
        for phrase in getattr(nation, "phrases", []):
            if phrase and phrase != nation.name and _is_plain_surface(phrase):
                terms.append(phrase)
    return _unique_preserve_order(_titlecase_surface(term) for term in terms)


def _currency_terms(currency_code: str) -> dict[str, list[str]]:
    props = MAJOR_CURRENCIES.get(currency_code, {})
    out: dict[str, list[str]] = {
        "symbol": [],
        "code": [],
        "name": [],
        "adjective": [],
        "adj_name": [],
    }

    out["symbol"] = _unique_preserve_order(
        sym for sym in props.get("symbols", []) if sym and _is_plain_surface(sym)
    )
    out["code"] = [currency_code.upper()]
    out["name"] = _unique_preserve_order(
        _titlecase_surface(name)
        for name in props.get("names", [])
        if name and _is_plain_surface(name)
    )
    adj = props.get("adj")
    if adj and _is_plain_surface(adj):
        out["adjective"] = [_titlecase_surface(str(adj))]
        adj_title = _titlecase_surface(str(adj))
        adj_names: list[str] = []
        for name in props.get("names", []):
            if not name or not _is_plain_surface(name):
                continue
            name_title = _titlecase_surface(name)
            if " " in name.strip():
                adj_names.append(name_title)
            else:
                adj_names.append(_titlecase_surface(f"{adj_title} {name_title}"))
        out["adj_name"] = _unique_preserve_order(adj_names)
    return out


_CURRENCY_UNIT_SURFACES: set[str] = {
    name.lower()
    for props in MAJOR_CURRENCIES.values()
    for name in props.get("names", [])
    if name and _is_plain_surface(name)
}


def _currency_is_suffix(currency_code: str | None) -> bool:
    if not currency_code:
        return False
    return bool(MAJOR_CURRENCIES.get(currency_code, {}).get("suffix"))


def _build_bundle(nation_code: str) -> FXBundle:
    nation = NATION_BY_CODE.get(nation_code.upper())
    if nation is None:
        raise KeyError(f"Unknown nation code: {nation_code!r}")

    compatible_currency_codes = sorted(NATION_TO_CURRENCY_CODES.get(nation_code.upper(), set()))
    currency_code = compatible_currency_codes[0] if compatible_currency_codes else None
    currency_terms = _currency_terms(currency_code) if currency_code else {}

    return FXBundle(
        nation_code=nation_code.upper(),
        nation_name=_titlecase_surface(nation.name),
        country_terms=tuple(_country_terms(nation)),
        adjective_terms=tuple(_adjective_terms(nation, currency_code)),
        city_terms=tuple(_flat_location_terms(nation)),
        currency_code=currency_code,
        currency_terms={k: tuple(v) for k, v in currency_terms.items()},
    )


FX_BUNDLES: dict[str, FXBundle] = {
    nation_code: _build_bundle(nation_code)
    for nation_code in NATION_BY_CODE
    if nation_code
}


def _pick_surface(candidates: Iterable[str], source_surface: str, rng: random.Random) -> str:
    pool = _unique_preserve_order(candidates)
    if not pool:
        return source_surface
    source_prefix = source_surface.lower().strip()[:3]
    prefix_matches = [term for term in pool if term.lower().strip()[:3] == source_prefix]
    if prefix_matches:
        return rng.choice(prefix_matches)
    return rng.choice(pool)


def _surface_is_plural_like(surface: str) -> bool:
    words = re.findall(r"[A-Za-z]+", surface)
    if not words:
        return False
    tail = words[-1].lower()
    if tail in {"us"}:
        return False
    return tail.endswith("s")


def _rank_currency_candidates(
    candidates: Iterable[str],
    source_surface: str,
    *,
    prefer_full_name: bool = False,
) -> list[str]:
    pool = _unique_preserve_order(candidates)
    if not pool:
        return []

    source_plural = _surface_is_plural_like(source_surface)
    same_number = [term for term in pool if _surface_is_plural_like(term) == source_plural]
    if same_number:
        pool = same_number

    if prefer_full_name:
        full_name = [term for term in pool if " " in term]
        if full_name:
            pool = full_name + [term for term in pool if term not in full_name]

    return pool


def _format_currency_surface(surface: str) -> str:
    """
    Normalize currency words for presentation.

    Symbols and ISO codes are preserved. Mixed-name surfaces like
    "british pound" become "British Pound".
    """
    if not surface:
        return surface
    if len(surface) <= 3 and surface.isupper():
        return surface
    if surface in {sym for props in MAJOR_CURRENCIES.values() for sym in props.get("symbols", [])}:
        return surface
    return _titlecase_surface(surface)


def _strip_leading_adjective(surface: str, adjectives: Iterable[str]) -> str:
    lower_surface = surface.lower().strip()
    for adjective in _unique_preserve_order(adjectives):
        adj = adjective.lower().strip()
        if not adj:
            continue
        if lower_surface.startswith(adj + " "):
            remainder = surface[len(adjective) :].lstrip(" -")
            return _titlecase_surface(remainder)
    return surface


def _compile_surface_regex(terms: Iterable[str]) -> re.Pattern[str] | None:
    terms = [term for term in terms if term]
    if not terms:
        return None
    escaped = [re.escape(term) for term in _unique_preserve_order(terms)]
    pattern = build_alternation(escaped)
    return re.compile(rf"(?<!\w)(?:{pattern})(?!\w)", re.IGNORECASE)


def _compile_symbol_regex(terms: Iterable[str]) -> re.Pattern[str] | None:
    terms = [term for term in terms if term]
    if not terms:
        return None
    escaped = [re.escape(term) for term in _unique_preserve_order(terms)]
    pattern = build_alternation(escaped)
    return re.compile(pattern)


def _build_term_index() -> tuple[
    dict[str, list[FXSurface]],
    re.Pattern[str] | None,
    re.Pattern[str] | None,
]:
    index: dict[str, list[FXSurface]] = {}
    word_terms: list[str] = []
    symbol_terms: list[str] = []

    def add(surface: str, kind: str, code: str, nation_code: str | None = None, currency_code: str | None = None) -> None:
        if not surface:
            return
        entry = FXSurface(
            kind=kind,
            code=code,
            surface=surface,
            nation_code=nation_code,
            currency_code=currency_code,
        )
        index.setdefault(surface.lower(), []).append(entry)
        if _is_word_surface(surface):
            word_terms.append(surface)
        else:
            symbol_terms.append(surface)

    for currency_code, props in MAJOR_CURRENCIES.items():
        amb_names = {name for name in props.get("amb_names", []) if name}
        for symbol in props.get("symbols", []):
            if symbol:
                add(symbol, "currency_symbol", currency_code, currency_code=currency_code)
        add(currency_code, "currency_code", currency_code, currency_code=currency_code)
        for name in props.get("names", []):
            if name and _is_plain_surface(name):
                if name in amb_names:
                    adj = props.get("adj")
                    if adj and _is_plain_surface(str(adj)):
                        add(
                            _titlecase_surface(f"{str(adj)} {name}"),
                            "currency_adj_name",
                            currency_code,
                            currency_code=currency_code,
                        )
                else:
                    add(_titlecase_surface(name), "currency_name", currency_code, currency_code=currency_code)
        adj = props.get("adj")
        if adj and _is_plain_surface(adj):
            add(_titlecase_surface(str(adj)), "currency_adjective", currency_code, currency_code=currency_code)

    for nation_code, nation in NATION_BY_CODE.items():
        add(nation.name, "country", nation_code, nation_code=nation_code)
        for phrase in getattr(nation, "phrases", []):
            if not phrase or not _is_plain_surface(phrase) or phrase == nation.name:
                continue
            if _looks_like_adjective(phrase):
                add(phrase, "adjective", nation_code, nation_code=nation_code)
            else:
                add(phrase, "country", nation_code, nation_code=nation_code)
        for location in getattr(nation, "locations", []):
            if location.name and _is_plain_surface(location.name):
                add(location.name, "city", nation_code, nation_code=nation_code)
            for phrase in getattr(location, "phrases", []):
                if phrase and _is_plain_surface(phrase):
                    add(phrase, "city", nation_code, nation_code=nation_code)
            for city in getattr(location, "cities", []):
                if city.name and _is_plain_surface(city.name):
                    add(city.name, "city", nation_code, nation_code=nation_code)
                for phrase in getattr(city, "phrases", []):
                    if phrase and _is_plain_surface(phrase):
                        add(phrase, "city", nation_code, nation_code=nation_code)

    word_regex = _compile_surface_regex(word_terms)
    symbol_regex = _compile_symbol_regex(symbol_terms)
    return index, word_regex, symbol_regex


TERM_INDEX, WORD_REGEX, SYMBOL_REGEX = _build_term_index()
TARGET_NATION_CODES = tuple(
    nation_code
    for nation_code in NATION_TO_CURRENCY_CODES
    if len(nation_code) == 2 and nation_code.isalpha() and nation_code != "EU"
)


def find_fx_hits(text: str) -> list[FXHit]:
    if not text:
        return []

    raw_hits: list[FXHit] = []

    if WORD_REGEX is not None:
        for match in WORD_REGEX.finditer(text):
            surface = match.group(0)
            entries = TERM_INDEX.get(surface.lower(), [])
            for entry in entries:
                if entry.surface.lower() == surface.lower():
                    raw_hits.append(
                        FXHit(
                            start=match.start(),
                            end=match.end(),
                            surface=surface,
                            kind=entry.kind,
                            nation_code=entry.nation_code,
                            currency_code=entry.currency_code,
                        )
                    )
                    break

    if SYMBOL_REGEX is not None:
        for match in SYMBOL_REGEX.finditer(text):
            surface = match.group(0)
            entries = TERM_INDEX.get(surface.lower(), [])
            for entry in entries:
                if entry.surface.lower() == surface.lower():
                    raw_hits.append(
                        FXHit(
                            start=match.start(),
                            end=match.end(),
                            surface=surface,
                            kind=entry.kind,
                            nation_code=entry.nation_code,
                            currency_code=entry.currency_code,
                        )
                    )
                    break

    raw_hits.sort(key=lambda hit: (hit.start, -(hit.end - hit.start)))

    selected: list[FXHit] = []
    cursor = -1
    for hit in raw_hits:
        if hit.start < cursor:
            continue
        selected.append(hit)
        cursor = hit.end

    merged: list[FXHit] = []
    idx = 0
    while idx < len(selected):
        hit = selected[idx]
        next_hit = selected[idx + 1] if idx + 1 < len(selected) else None
        if (
            next_hit is not None
            and hit.kind in {"adjective", "currency_adjective"}
            and next_hit.kind in {"currency_name", "currency_adj_name"}
            and next_hit.surface.lower() in _CURRENCY_UNIT_SURFACES
            and text[hit.end:next_hit.start].strip(" -") == ""
        ):
            merged.append(
                FXHit(
                    start=hit.start,
                    end=next_hit.end,
                    surface=text[hit.start:next_hit.end],
                    kind="currency_adj_name",
                    nation_code=hit.nation_code or next_hit.nation_code,
                    currency_code=next_hit.currency_code or hit.currency_code,
                )
            )
            idx += 2
            continue

        merged.append(hit)
        idx += 1

    return merged


def _find_exchange_rate_pairs(text: str, hits: list[FXHit]) -> list[tuple[FXHit, FXHit]]:
    ordered = sorted(hits, key=lambda hit: hit.start)
    pairs: list[tuple[FXHit, FXHit]] = []
    index = 0
    while index < len(ordered) - 1:
        left = ordered[index]
        right = ordered[index + 1]
        if right.start == left.end + 1 and text[left.end : right.start] == "/":
            if left.kind in {"currency_code", "currency_symbol"} and right.kind in {"currency_code", "currency_symbol"}:
                pairs.append((left, right))
                index += 2
                continue
        index += 1
    return pairs


def _currency_to_nations(currency_code: str | None) -> list[str]:
    if not currency_code:
        return []
    nation_codes = [
        nation_code
        for nation_code, currency_codes in NATION_TO_CURRENCY_CODES.items()
        if currency_code.upper() in currency_codes
    ]
    return nation_codes


def _infer_source_nation_code(hits: list[FXHit]) -> str | None:
    weights: dict[str, int] = {}
    for hit in hits:
        candidates = []
        if hit.nation_code:
            candidates.append(hit.nation_code)
        candidates.extend(_currency_to_nations(hit.currency_code))
        for nation_code in candidates:
            weights[nation_code] = weights.get(nation_code, 0) + 1
    if not weights:
        return None
    return max(weights.items(), key=lambda item: (item[1], -len(item[0])))[0]


def _pick_target_nation_code(
    source_nation_code: str | None,
    source_currency_codes: set[str] | None,
    rng: random.Random,
    used_target_nations: set[str] | None = None,
    used_target_currency_codes: set[str] | None = None,
) -> str:
    def _candidates(
        *,
        respect_used_nations: bool,
        respect_used_currencies: bool,
        respect_source_currencies: bool,
    ) -> list[str]:
        candidates: list[str] = []
        for nation_code in TARGET_NATION_CODES:
            if nation_code == source_nation_code:
                continue
            if respect_used_nations and used_target_nations is not None and nation_code in used_target_nations:
                continue
            target_bundle = FX_BUNDLES[nation_code]
            target_currency_code = target_bundle.currency_code
            if respect_used_currencies and used_target_currency_codes is not None and target_currency_code in used_target_currency_codes:
                continue
            if respect_source_currencies and source_currency_codes and target_currency_code in source_currency_codes:
                continue
            candidates.append(nation_code)
        rng.shuffle(candidates)
        return candidates

    for respect_used_nations, respect_used_currencies, respect_source_currencies in (
        (True, True, True),
        (True, False, True),
        (True, False, False),
        (False, False, False),
    ):
        candidates = _candidates(
            respect_used_nations=respect_used_nations,
            respect_used_currencies=respect_used_currencies,
            respect_source_currencies=respect_source_currencies,
        )
        if candidates:
            return candidates[0]
    raise ValueError("No target nation codes available")


def _group_key_for_hit(hit: FXHit) -> str:
    if hit.nation_code:
        return f"nation:{hit.nation_code}"
    if hit.currency_code:
        return f"currency:{hit.currency_code}"
    return "misc"


def _group_currency_codes(group_hits: list[FXHit]) -> set[str]:
    return {hit.currency_code for hit in group_hits if hit.currency_code}


def _replacement_for_hit(hit: FXHit, target: FXBundle, rng: random.Random) -> str:
    if hit.kind == "country":
        return _pick_surface(target.country_terms or (target.nation_name,), hit.surface, rng)
    if hit.kind == "adjective":
        return _pick_surface(target.adjective_terms or target.country_terms or (target.nation_name,), hit.surface, rng)
    if hit.kind == "city":
        return _pick_surface(target.city_terms or target.country_terms or (target.nation_name,), hit.surface, rng)
    if hit.kind == "currency_code":
        return _pick_surface(target.currency_terms.get("code", (hit.surface,)), hit.surface, rng)
    if hit.kind == "currency_symbol":
        return _pick_surface(target.currency_terms.get("symbol", (hit.surface,)), hit.surface, rng)
    if hit.kind == "currency_adjective":
        return _format_currency_surface(
            _pick_surface(target.currency_terms.get("adjective", ()) or target.currency_terms.get("name", ()), hit.surface, rng)
        )
    if hit.kind == "currency_adj_name":
        candidates = target.currency_terms.get("adj_name", ()) or target.currency_terms.get("name", ())
        ranked = _rank_currency_candidates(candidates, hit.surface, prefer_full_name=True)
        return _format_currency_surface(_pick_surface(ranked, hit.surface, rng))
    if hit.kind == "currency_name":
        candidates = target.currency_terms.get("adj_name", ()) + target.currency_terms.get("name", ())
        ranked = _rank_currency_candidates(candidates, hit.surface, prefer_full_name=True)
        chosen = _pick_surface(ranked, hit.surface, rng)
        return _format_currency_surface(chosen)
    return hit.surface


def _suffix_currency_replacement(
    text: str,
    hit: FXHit,
    target: FXBundle,
    rng: random.Random,
) -> dict[str, object] | None:
    if hit.kind not in {"currency_symbol", "currency_code"}:
        return None
    if not _currency_is_suffix(target.currency_code):
        return None

    tail = text[hit.end :]
    amount_match = _AMOUNT_AFTER_CURRENCY_RE.match(tail)
    if amount_match is None:
        return None

    suffix_token = _pick_surface(
        target.currency_terms.get("symbol", ())
        or target.currency_terms.get("code", ())
        or target.currency_terms.get("name", (hit.surface,)),
        hit.surface,
        rng,
    )
    suffix_token = _format_currency_surface(suffix_token)
    amount = amount_match.group("amount").strip()
    trailing = amount_match.group("trailing") or ""
    separator = trailing if trailing else " "
    return {
        "start": hit.start,
        "end": hit.end + amount_match.end(),
        "source": text[hit.start : hit.end + amount_match.end()],
        "target": f"{amount} {suffix_token}{separator}",
        "kind": "currency_suffix",
    }


def mutate_fx_text(
    text: str,
    *,
    rng: Optional[random.Random] = None,
    return_metadata: bool = False,
) -> str | tuple[str, dict[str, object]]:
    """
    Rewrite FX-like surfaces in a sentence using a coherent target bundle.

    The current implementation finds a source nation/currency bundle from the
    text, picks a different target nation bundle, and rewrites all matched FX
    surfaces consistently.
    """
    if rng is None:
        rng = random.Random()
    if not text:
        return (text, {"hits": [], "source": None, "target": None}) if return_metadata else text

    hits = find_fx_hits(text)
    if not hits:
        return (text, {"hits": [], "source": None, "target": None}) if return_metadata else text

    replacements: list[dict[str, object]] = []
    skipped: list[dict[str, object]] = []
    exchange_rate_replacements: list[dict[str, object]] = []
    exchange_rate_hits: set[FXHit] = set()
    for left, right in _find_exchange_rate_pairs(text, hits):
        exchange_rate_hits.add(left)
        exchange_rate_hits.add(right)
        pair_target = f"{right.surface}/{left.surface}"
        exchange_rate_replacements.append(
            {
                "start": left.start,
                "end": right.end,
                "source": f"{left.surface}/{right.surface}",
                "target": pair_target,
                "kind": "exchange_rate_pair",
            }
        )

    grouped_hits: dict[str, list[FXHit]] = {}
    for hit in hits:
        if hit in exchange_rate_hits:
            continue
        grouped_hits.setdefault(_group_key_for_hit(hit), []).append(hit)

    used_target_nations: set[str] = set()
    used_target_currency_codes: set[str] = set()
    grouped_metadata: list[dict[str, object]] = []
    for group_key, group_hits in grouped_hits.items():
        source_nation_code = _infer_source_nation_code(group_hits)
        source_currency_codes = _group_currency_codes(group_hits)
        if source_nation_code is None:
            source_nation_code = rng.choice(list(FX_BUNDLES.keys()))
        target_nation_code = _pick_target_nation_code(
            source_nation_code,
            source_currency_codes,
            rng,
            used_target_nations,
            used_target_currency_codes,
        )
        used_target_nations.add(target_nation_code)
        target_bundle = FX_BUNDLES[target_nation_code]
        if target_bundle.currency_code:
            used_target_currency_codes.add(target_bundle.currency_code)

        group_replacements: list[dict[str, object]] = []
        group_skipped: list[dict[str, object]] = []
        for hit in sorted(group_hits, key=lambda h: h.start, reverse=True):
            suffix_replacement = _suffix_currency_replacement(text, hit, target_bundle, rng)
            if suffix_replacement is not None:
                group_replacements.append(suffix_replacement)
                continue
            replacement = _replacement_for_hit(hit, target_bundle, rng)
            if not replacement:
                continue
            group_replacements.append(
                {
                    "start": hit.start,
                    "end": hit.end,
                    "source": hit.surface,
                    "target": replacement,
                    "kind": hit.kind,
                }
            )

        grouped_metadata.append(
            {
                "group": group_key,
                "source_nation_code": source_nation_code,
                "target_nation_code": target_nation_code,
                "target_currency_code": target_bundle.currency_code,
                "replacements": list(reversed(group_replacements)),
                "skipped": list(reversed(group_skipped)),
            }
        )

        replacements.extend(group_replacements)
        skipped.extend(group_skipped)
    replacements.extend(exchange_rate_replacements)

    mutated = text
    for item in sorted(replacements, key=lambda rec: rec["start"], reverse=True):
        start = int(item["start"])
        end = int(item["end"])
        target = str(item["target"])
        mutated = mutated[:start] + target + mutated[end:]

    metadata = {
        "source_nation_code": grouped_metadata[0]["source_nation_code"] if grouped_metadata else None,
        "target_nation_code": grouped_metadata[0]["target_nation_code"] if grouped_metadata else None,
        "target_currency_code": grouped_metadata[0]["target_currency_code"] if grouped_metadata else None,
        "groups": grouped_metadata,
        "exchange_rate_replacements": exchange_rate_replacements,
        "replacements": replacements,
        "skipped": skipped,
        "hits": [hit.__dict__ for hit in hits],
    }
    return (mutated, metadata) if return_metadata else mutated
