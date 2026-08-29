"""Catch the "no parameter(s) to optimize were found" failure before you run.

Freqtrade accepts ``--spaces buy`` against a strategy that declares no
optimizable parameters, then fails deep in the engine with::

    The 'buy' space is included in the hyperoptimization but no parameter(s)
    to optimize were found

That is a wasted setup at best, and on a long run a wasted queue slot. The check
is cheap and entirely static, so do it before you start.

``roi``, ``stoploss`` and ``trailing`` are excluded on purpose: freqtrade has
built-in optimisation ranges for those and they need no declared parameters.
"""

from __future__ import annotations

import re
from typing import Iterable

__all__ = [
    "SpaceRequiresParamsError",
    "normalize_spaces",
    "expand_spaces",
    "declares_optimizable_params",
    "validate_spaces_have_params",
    "SPACES_NEEDING_DECLARED_PARAMS",
]


class SpaceRequiresParamsError(ValueError):
    """A requested space needs declared parameters the strategy does not have."""


#: Spaces that require the strategy to declare at least one optimizable Parameter.
SPACES_NEEDING_DECLARED_PARAMS = frozenset({"buy", "sell", "protection"})

_SPLIT = re.compile(r"[\s,]+")

# Matches a freqtrade hyperopt Parameter declaration.
_PARAM_DECL = re.compile(r"\b(?:Int|Decimal|Real|Categorical|Boolean)Parameter\s*\(")
# An explicit optimize=False parameter is declared but NOT optimized, so it does
# not count toward "has optimizable params".
_OPTIMIZE_FALSE = re.compile(r"optimize\s*=\s*False")


def normalize_spaces(spaces: Iterable[str]) -> list[str]:
    """Flatten the ``spaces`` list into individual lowercased tokens.

    Freqtrade's idiom is multi-space (``--spaces buy roi stoploss``), and callers
    often pass that as a single element — ``"buy roi stoploss"`` or the comma
    form ``"roi,stoploss"``. Splitting on whitespace and commas accepts both.
    Order is preserved, duplicates dropped.
    """
    seen: set[str] = set()
    out: list[str] = []
    for raw in spaces:
        for tok in _SPLIT.split(raw or ""):
            t = tok.strip().lower()
            if not t or t in seen:
                continue
            seen.add(t)
            out.append(t)
    return out


def expand_spaces(spaces: Iterable[str]) -> set[str]:
    """Resolve freqtrade's aggregate spaces into the concrete ones they include.

    So a ``default`` or ``all`` request is checked for the buy/sell parameters it
    implicitly optimises. Other tokens pass through unchanged.
    """
    out: set[str] = set()
    for s in spaces:
        t = (s or "").strip().lower()
        if t == "default":
            out.update({"buy", "sell", "roi", "stoploss", "trailing"})
        elif t == "all":
            out.update({"buy", "sell", "roi", "stoploss", "trailing", "protection", "trades"})
        elif t:
            out.add(t)
    return out


def declares_optimizable_params(code: str) -> bool:
    """Does this strategy declare at least one optimizable hyperopt Parameter?

    Deliberately conservative: it scans line by line and returns False only when
    the code contains no optimizable Parameter declaration *at all*, so it never
    blocks a strategy that has parameters even if per-space attribution is
    imperfect. A declaration carrying ``optimize=False`` does not count.
    """
    for line in (code or "").splitlines():
        if _PARAM_DECL.search(line) and not _OPTIMIZE_FALSE.search(line):
            return True
    return False


def validate_spaces_have_params(spaces: Iterable[str], code: str) -> None:
    """Raise if a requested space needs declared parameters and there are none.

    Raises:
        SpaceRequiresParamsError: with the offending spaces named.
    """
    expanded = expand_spaces(spaces)
    need = sorted(expanded & SPACES_NEEDING_DECLARED_PARAMS)
    if not need:
        return
    if declares_optimizable_params(code):
        return
    raise SpaceRequiresParamsError(
        f"the {', '.join(need)} space(s) need at least one optimizable parameter, "
        "but this strategy declares none — add hyperopt parameters "
        "(IntParameter, DecimalParameter, ...), or optimize roi/stoploss/trailing instead"
    )
