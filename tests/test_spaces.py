"""The pre-flight check for freqtrade's "no parameter(s) to optimize" failure."""

from __future__ import annotations

import pytest

from freqtrade_hyperopt_guard.spaces import (
    SpaceRequiresParamsError,
    declares_optimizable_params,
    expand_spaces,
    normalize_spaces,
    validate_spaces_have_params,
)

WITH_PARAMS = """
class MyStrat(IStrategy):
    buy_rsi = IntParameter(10, 40, default=30, space="buy")
"""

NO_PARAMS = """
class MyStrat(IStrategy):
    def populate_entry_trend(self, df, meta):
        return df
"""

ONLY_FROZEN = """
class MyStrat(IStrategy):
    buy_rsi = IntParameter(10, 40, default=30, space="buy", optimize=False)
"""


@pytest.mark.parametrize(
    "raw,expected",
    [
        (["buy", "sell"], ["buy", "sell"]),
        (["buy roi stoploss"], ["buy", "roi", "stoploss"]),      # the freqtrade idiom in one element
        (["roi,stoploss"], ["roi", "stoploss"]),                  # comma form
        (["BUY", "buy", " Sell "], ["buy", "sell"]),              # case + dupes + padding
        ([""], []),
    ],
)
def test_normalize_spaces(raw, expected):
    assert normalize_spaces(raw) == expected


def test_aggregates_expand():
    assert "buy" in expand_spaces(["default"])
    assert "protection" in expand_spaces(["all"])
    assert "protection" not in expand_spaces(["default"])


def test_roi_and_stoploss_need_no_declared_params():
    """Freqtrade optimises these natively, so they must never be blocked."""
    validate_spaces_have_params(["roi", "stoploss", "trailing"], NO_PARAMS)


def test_buy_space_without_params_is_rejected():
    with pytest.raises(SpaceRequiresParamsError) as exc:
        validate_spaces_have_params(["buy"], NO_PARAMS)
    assert "buy" in str(exc.value)


def test_aggregate_space_is_checked_for_what_it_implies():
    with pytest.raises(SpaceRequiresParamsError):
        validate_spaces_have_params(["all"], NO_PARAMS)


def test_declared_params_pass():
    validate_spaces_have_params(["buy", "sell"], WITH_PARAMS)


def test_optimize_false_does_not_count():
    assert not declares_optimizable_params(ONLY_FROZEN)
    with pytest.raises(SpaceRequiresParamsError):
        validate_spaces_have_params(["buy"], ONLY_FROZEN)
