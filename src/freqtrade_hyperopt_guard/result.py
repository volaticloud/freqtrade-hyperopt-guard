"""Read Freqtrade's own ``.fthypt`` hyperopt result file.

``.fthypt`` is JSON Lines: one JSON object per line, one line per epoch, each
carrying ``loss``, ``params_dict`` and ``results_metrics``. Freqtrade does not
number the epochs in the file — the line number *is* the epoch number, 1-based —
so that is injected here, matching what freqtrade's own reporting shows you.

Find yours at::

    user_data/hyperopt_results/*.fthypt
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Iterator

__all__ = ["HyperoptResultError", "load_result", "parse_fthypt"]


class HyperoptResultError(ValueError):
    """The file is not a Freqtrade hyperopt result we can read."""


def _iter_epochs(text: str) -> Iterator[dict[str, Any]]:
    """Yield epochs, skipping unparseable lines.

    A truncated final line is normal — the file is appended to while the run is
    still going, so reading it live catches a half-written record. One bad line
    must not lose the other 99 epochs.
    """
    for i, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            epoch = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(epoch, dict):
            continue
        epoch["epoch_number"] = i
        yield epoch


def parse_fthypt(text: str) -> dict[str, Any]:
    """Turn ``.fthypt`` text into a result object ``select_best_epoch`` accepts.

    ``best_epoch`` / ``best_result`` reproduce freqtrade's own choice — lowest
    loss wins — so the selector can be compared against it.
    """
    epochs: list[dict[str, Any]] = []
    best: dict[str, Any] | None = None
    best_loss = math.inf

    for epoch in _iter_epochs(text):
        epochs.append(epoch)
        loss = epoch.get("loss")
        if isinstance(loss, (int, float)) and not isinstance(loss, bool) and loss < best_loss:
            best_loss, best = float(loss), epoch

    if not epochs:
        raise HyperoptResultError(
            "no readable epochs — expected Freqtrade's JSON-Lines .fthypt "
            "(one JSON object per line), usually under user_data/hyperopt_results/"
        )

    result: dict[str, Any] = {"epochs_data": epochs, "current_epoch": len(epochs)}
    if best is not None:
        result["best_epoch"] = best["epoch_number"]
        result["best_result"] = best
        result["best_loss"] = best_loss
    return result


def load_result(path: str | Path) -> dict[str, Any]:
    """Read a ``.fthypt`` file and return a result object for the selector."""
    p = Path(path)
    try:
        text = p.read_text()
    except OSError as exc:
        raise HyperoptResultError(f"{p}: {exc}") from exc
    return parse_fthypt(text)
