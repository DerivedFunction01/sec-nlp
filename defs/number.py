from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Literal, Optional, Sequence

Number = int | float

Strategy = Literal[
    "random",
    "preserve",
    "shared_scale",
    "shared_offset",
    "shared_affine",
    "independent_scale",
    "independent_offset",
]


@dataclass(frozen=True)
class NumberMutationPlan:
    """
    Describes how a batch of numbers was mutated.

    This is optional metadata for callers that want to preserve the exact
    transformation that was applied to a label group.
    """

    strategy: str
    scale: float | None = None
    offset: float | None = None


def _as_float(value: Number) -> float:
    if isinstance(value, bool):
        raise TypeError("bool is not a supported numeric input")
    return float(value)


def _maybe_round(value: float, int_only: bool) -> Number:
    if int_only:
        return int(round(value))
    return value


def _enforce_constraints(
    value: float,
    *,
    allow_zero: bool,
    allow_negative: bool,
    lower_bound: float | None = None,
    upper_bound: float | None = None,
    clamp: bool = True,
    min_magnitude: float = 1.0,
) -> float:
    if not allow_negative and value < 0:
        value = abs(value)

    if not allow_zero and value == 0:
        value = min_magnitude
        if not allow_negative and value < 0:
            value = abs(value)

    if lower_bound is not None and upper_bound is not None and lower_bound > upper_bound:
        raise ValueError("lower_bound cannot be greater than upper_bound")

    if lower_bound is not None and value < lower_bound:
        if clamp:
            value = lower_bound
    if upper_bound is not None and value > upper_bound:
        if clamp:
            value = upper_bound

    return value


def _pick_strategy(strategy: Strategy, numbers: Sequence[Number], rng: random.Random) -> str:
    if strategy != "random":
        return strategy

    candidates = ["shared_scale", "shared_offset", "shared_affine"]
    if len(numbers) <= 1:
        candidates.extend(["independent_scale", "independent_offset"])
    return rng.choice(candidates)


def _shared_scale_factor(numbers: Sequence[Number], rng: random.Random) -> float:
    magnitudes = [abs(_as_float(n)) for n in numbers if _as_float(n) != 0]
    if not magnitudes:
        return rng.uniform(1.2, 4.0)

    max_mag = max(magnitudes)
    if max_mag < 10:
        return rng.uniform(1.5, 6.0)
    if max_mag < 100:
        return rng.uniform(1.2, 4.0)
    if max_mag < 1_000:
        return rng.uniform(0.75, 3.0)
    if max_mag < 100_000:
        return rng.uniform(0.25, 3.0)
    return rng.uniform(0.05, 2.0)


def _shared_offset_value(numbers: Sequence[Number], rng: random.Random) -> float:
    magnitudes = [abs(_as_float(n)) for n in numbers]
    scale = max(magnitudes, default=1.0)
    if scale < 10:
        scale = 10.0
    return rng.uniform(-0.75 * scale, 0.75 * scale)


def _independent_scale_factor(number: Number, rng: random.Random) -> float:
    magnitude = abs(_as_float(number))
    if magnitude < 10:
        return rng.uniform(1.5, 6.0)
    if magnitude < 100:
        return rng.uniform(1.2, 4.0)
    if magnitude < 1_000:
        return rng.uniform(0.75, 3.0)
    if magnitude < 100_000:
        return rng.uniform(0.25, 3.0)
    return rng.uniform(0.05, 2.0)


def _independent_offset_value(number: Number, rng: random.Random) -> float:
    magnitude = abs(_as_float(number))
    if magnitude < 10:
        magnitude = 10.0
    return rng.uniform(-0.75 * magnitude, 0.75 * magnitude)


def _apply_shared_scale(
    numbers: Sequence[Number],
    *,
    int_only: bool,
    allow_zero: bool,
    allow_negative: bool,
    lower_bound: float | None,
    upper_bound: float | None,
    clamp: bool,
    rng: random.Random,
) -> tuple[list[Number], NumberMutationPlan]:
    factor = _shared_scale_factor(numbers, rng)
    mutated: list[Number] = []
    for number in numbers:
        new_value = _as_float(number) * factor
        new_value = _enforce_constraints(
            new_value,
            allow_zero=allow_zero,
            allow_negative=allow_negative,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            clamp=clamp,
            min_magnitude=max(1.0, abs(_as_float(number))),
        )
        mutated.append(_maybe_round(new_value, int_only))
    return mutated, NumberMutationPlan(strategy="shared_scale", scale=factor)


def _apply_shared_offset(
    numbers: Sequence[Number],
    *,
    int_only: bool,
    allow_zero: bool,
    allow_negative: bool,
    lower_bound: float | None,
    upper_bound: float | None,
    clamp: bool,
    rng: random.Random,
) -> tuple[list[Number], NumberMutationPlan]:
    offset = _shared_offset_value(numbers, rng)
    mutated: list[Number] = []
    for number in numbers:
        new_value = _as_float(number) + offset
        new_value = _enforce_constraints(
            new_value,
            allow_zero=allow_zero,
            allow_negative=allow_negative,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            clamp=clamp,
            min_magnitude=max(1.0, abs(_as_float(number))),
        )
        mutated.append(_maybe_round(new_value, int_only))
    return mutated, NumberMutationPlan(strategy="shared_offset", offset=offset)


def _apply_shared_affine(
    numbers: Sequence[Number],
    *,
    int_only: bool,
    allow_zero: bool,
    allow_negative: bool,
    lower_bound: float | None,
    upper_bound: float | None,
    clamp: bool,
    rng: random.Random,
) -> tuple[list[Number], NumberMutationPlan]:
    factor = _shared_scale_factor(numbers, rng)
    offset = _shared_offset_value(numbers, rng)
    mutated: list[Number] = []
    for number in numbers:
        new_value = (_as_float(number) * factor) + offset
        new_value = _enforce_constraints(
            new_value,
            allow_zero=allow_zero,
            allow_negative=allow_negative,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            clamp=clamp,
            min_magnitude=max(1.0, abs(_as_float(number))),
        )
        mutated.append(_maybe_round(new_value, int_only))
    return mutated, NumberMutationPlan(
        strategy="shared_affine",
        scale=factor,
        offset=offset,
    )


def _apply_independent_scale(
    numbers: Sequence[Number],
    *,
    int_only: bool,
    allow_zero: bool,
    allow_negative: bool,
    lower_bound: float | None,
    upper_bound: float | None,
    clamp: bool,
    rng: random.Random,
) -> tuple[list[Number], NumberMutationPlan]:
    mutated: list[Number] = []
    for number in numbers:
        factor = _independent_scale_factor(number, rng)
        new_value = _as_float(number) * factor
        new_value = _enforce_constraints(
            new_value,
            allow_zero=allow_zero,
            allow_negative=allow_negative,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            clamp=clamp,
            min_magnitude=max(1.0, abs(_as_float(number))),
        )
        mutated.append(_maybe_round(new_value, int_only))
    return mutated, NumberMutationPlan(strategy="independent_scale")


def _apply_independent_offset(
    numbers: Sequence[Number],
    *,
    int_only: bool,
    allow_zero: bool,
    allow_negative: bool,
    lower_bound: float | None,
    upper_bound: float | None,
    clamp: bool,
    rng: random.Random,
) -> tuple[list[Number], NumberMutationPlan]:
    mutated: list[Number] = []
    for number in numbers:
        offset = _independent_offset_value(number, rng)
        new_value = _as_float(number) + offset
        new_value = _enforce_constraints(
            new_value,
            allow_zero=allow_zero,
            allow_negative=allow_negative,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            clamp=clamp,
            min_magnitude=max(1.0, abs(_as_float(number))),
        )
        mutated.append(_maybe_round(new_value, int_only))
    return mutated, NumberMutationPlan(strategy="independent_offset")


def mutate_numbers(
    numbers: Sequence[Number],
    *,
    strategy: Strategy = "random",
    int_only: bool = True,
    allow_zero: bool = True,
    allow_negative: bool = True,
    lower_bound: float | None = None,
    upper_bound: float | None = None,
    clamp: bool = True,
    strict: bool = False,
    rng: Optional[random.Random] = None,
    return_plan: bool = False,
) -> list[Number] | tuple[list[Number], NumberMutationPlan]:
    """
    Mutate a batch of numeric values in parallel.

    The batch shares one strategy by default so related numbers stay coherent.
    """

    if rng is None:
        rng = random.Random()

    values = list(numbers)
    if not values:
        empty_plan = NumberMutationPlan(strategy="preserve")
        return ([], empty_plan) if return_plan else []

    if lower_bound is not None and upper_bound is not None and lower_bound > upper_bound:
        raise ValueError("lower_bound cannot be greater than upper_bound")

    chosen = _pick_strategy(strategy, values, rng)

    def _finalize(
        mutated_values: list[Number],
        plan: NumberMutationPlan,
    ) -> tuple[list[Number], NumberMutationPlan]:
        if strict and (lower_bound is not None or upper_bound is not None):
            finalized: list[Number] = []
            for item in mutated_values:
                as_float = _as_float(item)
                if lower_bound is not None and as_float < lower_bound:
                    raise ValueError(
                        f"Mutated value {item} fell below lower_bound={lower_bound}"
                    )
                if upper_bound is not None and as_float > upper_bound:
                    raise ValueError(
                        f"Mutated value {item} exceeded upper_bound={upper_bound}"
                    )
                finalized.append(item)
            return finalized, plan
        return mutated_values, plan

    if chosen == "preserve":
        mutated = [
            _maybe_round(
                _enforce_constraints(
                    _as_float(number),
                    allow_zero=allow_zero,
                    allow_negative=allow_negative,
                    lower_bound=lower_bound,
                    upper_bound=upper_bound,
                    clamp=clamp,
                    min_magnitude=max(1.0, abs(_as_float(number))),
                ),
                int_only,
            )
            for number in values
        ]
        plan = NumberMutationPlan(strategy="preserve")
    elif chosen == "shared_scale":
        mutated, plan = _apply_shared_scale(
            values,
            int_only=int_only,
            allow_zero=allow_zero,
            allow_negative=allow_negative,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            clamp=clamp,
            rng=rng,
        )
    elif chosen == "shared_offset":
        mutated, plan = _apply_shared_offset(
            values,
            int_only=int_only,
            allow_zero=allow_zero,
            allow_negative=allow_negative,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            clamp=clamp,
            rng=rng,
        )
    elif chosen == "shared_affine":
        mutated, plan = _apply_shared_affine(
            values,
            int_only=int_only,
            allow_zero=allow_zero,
            allow_negative=allow_negative,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            clamp=clamp,
            rng=rng,
        )
    elif chosen == "independent_scale":
        mutated, plan = _apply_independent_scale(
            values,
            int_only=int_only,
            allow_zero=allow_zero,
            allow_negative=allow_negative,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            clamp=clamp,
            rng=rng,
        )
    elif chosen == "independent_offset":
        mutated, plan = _apply_independent_offset(
            values,
            int_only=int_only,
            allow_zero=allow_zero,
            allow_negative=allow_negative,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            clamp=clamp,
            rng=rng,
        )
    else:
        raise ValueError(
            f"Unknown strategy '{chosen}'. "
            "Use one of: preserve, shared_scale, shared_offset, shared_affine, "
            "independent_scale, independent_offset, random."
        )

    mutated, plan = _finalize(mutated, plan)
    return (mutated, plan) if return_plan else mutated


def mutate_number(
    number: Number,
    *,
    strategy: Strategy = "random",
    int_only: bool = True,
    allow_zero: bool = True,
    allow_negative: bool = True,
    lower_bound: float | None = None,
    upper_bound: float | None = None,
    clamp: bool = True,
    strict: bool = False,
    rng: Optional[random.Random] = None,
    return_plan: bool = False,
) -> Number | tuple[Number, NumberMutationPlan]:
    """
    Convenience wrapper for a single number.
    """

    result = mutate_numbers(
        [number],
        strategy=strategy,
        int_only=int_only,
        allow_zero=allow_zero,
        allow_negative=allow_negative,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
        clamp=clamp,
        strict=strict,
        rng=rng,
        return_plan=return_plan,
    )

    if return_plan:
        assert isinstance(result, tuple)
        mutated, plan = result
        return mutated[0], plan

    assert not isinstance(result, tuple)
    return result[0]
