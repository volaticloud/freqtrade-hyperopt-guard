"""Re-select a hyperopt winner under a quality floor.

Freqtrade's hyperopt loss functions carry **no minimum-trade-count constraint**.
The optimiser minimises loss and nothing else, so a search that stumbles on
parameters entering twice in ten months and winning both times scores a superb
Sharpe on a sample of two — and that is returned as the best epoch, with nothing
marking it as untradeable.

This treats the optimiser's pick as an *input*, not the authority. Freqtrade
ships every evaluated epoch in ``epochs_data``, so the winner is re-selected
from the full set subject to a floor. Among epochs that clear the floor the same
rule the optimiser uses applies — lowest loss wins, earliest epoch breaks a tie
— so a run whose best epoch is already tradeable is left alone.

When *nothing* clears the floor the optimiser's pick is still returned, with
:attr:`EpochSelection.degenerate` set. Reporting the least-bad untradeable epoch
as "the best parameters" without saying so is the defect.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

__all__ = ["EpochFloor", "EpochSelection", "DEFAULT_EPOCH_FLOOR", "select_best_epoch"]


@dataclass(frozen=True)
class EpochFloor:
    """The minimum evidence an epoch must show to be worth acting on.

    A parameter rather than a constant, because the right threshold depends on
    timeframe and window: 50 trades is thin for a 5m strategy over a year and
    unreachable for a 1d strategy over a month.
    """

    #: Smallest trade count an epoch may report. 0 disables the test.
    min_trades: int = 50
    #: Value the profit factor must EXCEED — not merely equal. 0 disables the test.
    min_profit_factor: float = 1.0

    def qualifies(self, metrics: Optional[Mapping[str, Any]]) -> bool:
        """Does one epoch's ``results_metrics`` block clear this floor?

        Profit factor is deliberately forgiving when **absent or non-finite**:
        freqtrade emits ``Infinity`` for an epoch with zero losing trades, and
        some pipelines drop it entirely. Treating that as a failure would
        discard the best epochs of a strongly trending run. A missing profit
        factor therefore leaves the trade count as the only evidence — which is
        why a thin epoch with no profit factor is still rejected.
        """
        if metrics is None:
            return False
        if self.min_trades > 0 and _epoch_trade_count(metrics) < self.min_trades:
            return False
        if self.min_profit_factor > 0:
            pf = _get_float_or_none(metrics, "profit_factor")
            if pf is not None and not math.isinf(pf) and not math.isnan(pf):
                if pf <= self.min_profit_factor:
                    return False
        return True


#: Applied when a run does not choose its own floor.
DEFAULT_EPOCH_FLOOR = EpochFloor(min_trades=50, min_profit_factor=1.0)


@dataclass(frozen=True)
class EpochSelection:
    """The outcome of re-selecting a winner from the full epoch set."""

    #: The winning epoch object, or None when the result carried nothing usable.
    epoch: Optional[Mapping[str, Any]] = None
    #: The winning epoch's 1-based index.
    number: int = 0
    #: How many epochs cleared the floor.
    eligible: int = 0
    #: How many epochs could actually be READ. Zero means no usable
    #: ``epochs_data``: the optimiser's choice stands and ``degenerate`` is
    #: meaningless.
    considered: int = 0
    #: True when epochs were evaluated and NONE cleared the floor. The
    #: optimiser's pick is still reported so you can see what happened; this
    #: flag is what stops it being read as a usable result.
    degenerate: bool = False


def _get_number(m: Mapping[str, Any], key: str) -> Optional[float]:
    """Read a numeric value, ignoring strings and other non-numbers.

    bool is excluded deliberately: in Python ``True`` is an int, and a stray
    boolean must not be read as the number 1.
    """
    v = m.get(key)
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return float(v)


def _get_int(m: Mapping[str, Any], key: str) -> int:
    v = _get_number(m, key)
    return 0 if v is None else int(v)


def _get_float(m: Mapping[str, Any], key: str) -> float:
    v = _get_number(m, key)
    return 0.0 if v is None else v


def _get_float_or_none(m: Mapping[str, Any], key: str) -> Optional[float]:
    return _get_number(m, key)


def _epoch_trade_count(metrics: Mapping[str, Any]) -> int:
    """Accepts the current key and the legacy one older runs still produce."""
    if "total_trades" in metrics:
        return _get_int(metrics, "total_trades")
    return _get_int(metrics, "trade_count")


def select_best_epoch(
    raw_result: Mapping[str, Any],
    floor: EpochFloor = DEFAULT_EPOCH_FLOOR,
) -> EpochSelection:
    """Re-select the winning epoch from ``epochs_data`` under ``floor``.

    Falls back to the optimiser's own ``best_epoch`` / ``best_result`` when
    there is no epoch data to re-select on.
    """
    fallback_epoch = None
    best_result = raw_result.get("best_result")
    if isinstance(best_result, Mapping) and len(best_result) > 0:
        fallback_epoch = best_result
    fallback_number = _get_int(raw_result, "best_epoch")

    epochs = raw_result.get("epochs_data")
    if not isinstance(epochs, Sequence) or isinstance(epochs, (str, bytes)) or len(epochs) == 0:
        # No evidence to re-select on (a legacy row, or a mid-run snapshot).
        # Never label that degenerate.
        return EpochSelection(epoch=fallback_epoch, number=fallback_number)

    considered = 0
    eligible = 0
    best_epoch: Optional[Mapping[str, Any]] = None
    best_number = 0
    best_loss = 0.0
    found = False

    for i, raw in enumerate(epochs):
        if not isinstance(raw, Mapping):
            continue
        considered += 1

        metrics = raw.get("results_metrics")
        if not isinstance(metrics, Mapping):
            metrics = None
        if not floor.qualifies(metrics):
            continue
        eligible += 1

        number = _get_int(raw, "epoch_number") or (i + 1)
        loss = _get_float(raw, "loss")
        if not found or loss < best_loss or (loss == best_loss and number < best_number):
            best_epoch, best_number, best_loss, found = raw, number, loss, True

    if not found:
        # Only a run whose epochs were READ and all fell below the floor is
        # degenerate. If none parsed there is no evidence either way, and
        # calling that "no tradeable epoch" would be a claim we cannot make.
        return EpochSelection(
            epoch=fallback_epoch,
            number=fallback_number,
            eligible=eligible,
            considered=considered,
            degenerate=considered > 0,
        )

    return EpochSelection(
        epoch=best_epoch,
        number=best_number,
        eligible=eligible,
        considered=considered,
        degenerate=False,
    )
