"""Read Freqtrade's own ``.fthypt`` hyperopt result file.

``.fthypt`` is JSON Lines: one JSON object per line, one line per epoch, each
carrying ``loss``, ``params_dict``, ``results_metrics`` and ``current_epoch``.
Freqtrade's own writer says so plainly — *"Store one line per epoch. While not a
valid json object - this allows appending easily."*

Two things about the format that bite naive readers:

**It is not strict JSON.** Freqtrade dumps with
``rapidjson.NM_NATIVE | rapidjson.NM_NAN``, so a metric can appear as bare
``Infinity``, ``-Infinity`` or ``NaN`` — tokens RFC 8259 does not allow. Python's
``json`` accepts them by default and yields the float; stricter parsers reject
the line outright. That is why an infinite profit factor has to be handled as a
value here rather than assumed impossible.

**Epoch numbers come from the file, not from line position.** Freqtrade sets
``current_epoch`` on every epoch before writing it. Line position happens to
agree for a single complete run, but not for a file that was filtered,
concatenated, or resumed — and a tool reporting "epoch 12" while
``freqtrade hyperopt-list`` says "epoch 47" is worse than useless. So
``current_epoch`` wins, and the line number is only a fallback for a file that
somehow lacks it.

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
        # Prefer freqtrade's own numbering; fall back to line position.
        n = epoch.get("current_epoch")
        epoch["epoch_number"] = int(n) if isinstance(n, int) and not isinstance(n, bool) else i
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
