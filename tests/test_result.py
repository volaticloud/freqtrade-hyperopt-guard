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


def test_epoch_number_comes_from_freqtrade_not_line_position():
    """Freqtrade sets `current_epoch` on every epoch before writing it
    (hyperopt.py: evaluate_result -> _save_result), so that is authoritative.

    Line position only agrees for a single complete run -- not for a file that
    was filtered, concatenated or resumed. Reporting "epoch 12" while
    `freqtrade hyperopt-list` says "epoch 47" is worse than useless.
    """
    numbered = (
        '{"current_epoch":47,"loss":-0.42,"results_metrics":{"total_trades":184}}\n'
        '{"current_epoch":48,"loss":-0.91,"results_metrics":{"total_trades":2}}\n'
    )
    result = parse_fthypt(numbered)
    assert [e["epoch_number"] for e in result["epochs_data"]] == [47, 48]
    assert result["best_epoch"] == 48


def test_line_position_is_only_a_fallback():
    """A file lacking current_epoch still gets usable 1-based numbering."""
    result = parse_fthypt(FTHYPT)
    assert [e["epoch_number"] for e in result["epochs_data"]] == [1, 2, 3]


def test_bare_Infinity_is_read_as_a_float_not_a_parse_error():
    """freqtrade dumps with rapidjson NM_NATIVE|NM_NAN, so .fthypt legitimately
    contains bare Infinity/NaN -- tokens RFC 8259 forbids. Python accepts them;
    stricter parsers reject the whole line."""
    import math
    r = parse_fthypt('{"loss":-0.5,"results_metrics":{"total_trades":60,"profit_factor":Infinity}}')
    assert r["epochs_data"][0]["results_metrics"]["profit_factor"] == math.inf


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
