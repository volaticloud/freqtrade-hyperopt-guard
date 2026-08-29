"""Cross-implementation golden vectors for epoch selection.

The rule lives twice: in Go inside VolatiCloud and here in Python. The rule *is*
the product — "the optimiser's pick is an input, not the authority" — so the two
disagreeing about which epoch wins is the worst failure either can have.

``testdata/selection_vectors.json`` is generated from the Go implementation.
A failure here means they have drifted; fix the code, never the file.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from freqtrade_hyperopt_guard.selection import (
    DEFAULT_EPOCH_FLOOR,
    EpochFloor,
    select_best_epoch,
)

VECTORS = json.loads((Path(__file__).parent / "testdata" / "selection_vectors.json").read_text())


@pytest.mark.parametrize("case", VECTORS, ids=[c["name"] for c in VECTORS])
def test_matches_reference_implementation(case):
    floor = EpochFloor(
        min_trades=case["floor"]["minTrades"],
        min_profit_factor=case["floor"]["minProfitFactor"],
    )
    got = select_best_epoch(case["raw"], floor)
    want = case["expected"]

    assert got.number == want["number"], "the Go and Python implementations have drifted"
    assert got.eligible == want["eligible"]
    assert got.considered == want["considered"]
    assert got.degenerate == want["degenerate"]
    assert (got.epoch is not None) == want["hasEpoch"]


def test_vector_file_keeps_its_dangerous_cases():
    names = {c["name"] for c in VECTORS}
    for required in (
        "thin_best_epoch_is_overridden",
        "all_below_floor_is_degenerate",
        "no_epochs_data_is_not_degenerate",
        "profit_factor_equal_to_floor_is_rejected",
        "loss_tie_breaks_on_earliest_epoch",
    ):
        assert required in names, f"vector file lost the {required!r} case"


@pytest.mark.parametrize("pf", [math.inf, -math.inf, math.nan], ids=["+inf", "-inf", "nan"])
def test_non_finite_profit_factor(pf):
    """The branch the shared vector file structurally cannot carry.

    Freqtrade writes bare ``Infinity`` into .fthypt for an epoch with zero
    losing trades. Python's json.loads yields float('inf') from that, so this
    port meets real infinities in the wild — Go's encoding/json refuses to parse
    the same token, which is why it cannot appear in the shared vector file.

    A non-finite profit factor must be treated as absent: it neither
    disqualifies a well-traded epoch nor rescues a thin one.
    """
    assert DEFAULT_EPOCH_FLOOR.qualifies({"total_trades": 60, "profit_factor": pf})
    assert not DEFAULT_EPOCH_FLOOR.qualifies({"total_trades": 3, "profit_factor": pf})


def test_freqtrade_really_writes_a_token_python_reads_as_inf():
    """Guards the assumption the test above rests on."""
    assert json.loads('{"profit_factor": Infinity}')["profit_factor"] == math.inf


def test_booleans_are_not_read_as_numbers():
    """In Python bool is an int; a stray True must not count as 1 trade."""
    assert not DEFAULT_EPOCH_FLOOR.qualifies({"total_trades": True})
