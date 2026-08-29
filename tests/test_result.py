"""Reading freqtrade's native .fthypt (JSON Lines, one epoch per line)."""

from __future__ import annotations

import math

import pytest

from freqtrade_hyperopt_guard.result import HyperoptResultError, parse_fthypt
from freqtrade_hyperopt_guard.selection import select_best_epoch

FTHYPT = (
    '{"loss":-0.42,"results_metrics":{"total_trades":184,"profit_factor":1.61}}\n'
    '{"loss":-0.91,"results_metrics":{"total_trades":2,"profit_factor":Infinity}}\n'
    '{"loss":-0.11,"results_metrics":{"total_trades":95,"profit_factor":1.08}}\n'
)


def test_epoch_number_is_the_1_based_line_number():
    result = parse_fthypt(FTHYPT)
    assert [e["epoch_number"] for e in result["epochs_data"]] == [1, 2, 3]


def test_best_epoch_reproduces_freqtrades_own_choice():
    """Lowest loss wins — including the 2-trade epoch. That is the defect."""
    result = parse_fthypt(FTHYPT)
    assert result["best_epoch"] == 2
    assert result["best_loss"] == -0.91


def test_the_guard_overrides_that_choice():
    sel = select_best_epoch(parse_fthypt(FTHYPT))
    assert sel.number == 1, "the 184-trade epoch should win once the floor applies"
    assert sel.eligible == 2
    assert sel.considered == 3
    assert not sel.degenerate


def test_a_truncated_final_line_is_skipped_not_fatal():
    """The file is appended to during a run, so a live read catches half a line.
    One bad line must not lose the other epochs."""
    result = parse_fthypt(FTHYPT + '{"loss":-0.5,"results_met')
    assert len(result["epochs_data"]) == 3


def test_blank_lines_are_ignored():
    assert len(parse_fthypt("\n\n" + FTHYPT + "\n")["epochs_data"]) == 3


def test_a_file_with_nothing_readable_raises():
    with pytest.raises(HyperoptResultError):
        parse_fthypt("not json at all\n")
