"""Stop a hyperopt run from handing you untradeable parameters.

Two guards, both static and both cheap:

**Before the run** — catch the "no parameter(s) to optimize were found" failure
that freqtrade only raises deep in the engine::

    from freqtrade_hyperopt_guard import validate_spaces_have_params
    validate_spaces_have_params(["buy", "sell"], strategy_source)

**After the run** — re-pick the winner under a quality floor, because freqtrade's
loss functions have no minimum-trade-count constraint::

    from freqtrade_hyperopt_guard import select_best_epoch, load_result

    sel = select_best_epoch(load_result("strategy.fthypt"))
    if sel.degenerate:
        print("no epoch cleared the floor — do not trade these parameters")
    else:
        print("winning epoch", sel.number, "of", sel.considered)
"""

from .result import HyperoptResultError, load_result
from .selection import (
    DEFAULT_EPOCH_FLOOR,
    EpochFloor,
    EpochSelection,
    select_best_epoch,
)
from .spaces import (
    SPACES_NEEDING_DECLARED_PARAMS,
    SpaceRequiresParamsError,
    declares_optimizable_params,
    expand_spaces,
    normalize_spaces,
    validate_spaces_have_params,
)

__version__ = "0.1.0"

__all__ = [
    "DEFAULT_EPOCH_FLOOR",
    "EpochFloor",
    "EpochSelection",
    "HyperoptResultError",
    "SPACES_NEEDING_DECLARED_PARAMS",
    "SpaceRequiresParamsError",
    "declares_optimizable_params",
    "expand_spaces",
    "load_result",
    "normalize_spaces",
    "select_best_epoch",
    "validate_spaces_have_params",
]
