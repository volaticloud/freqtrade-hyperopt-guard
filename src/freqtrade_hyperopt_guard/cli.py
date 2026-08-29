"""Command line interface.

    freqtrade-hyperopt-guard select user_data/hyperopt_results/*.fthypt
    freqtrade-hyperopt-guard check-spaces --spaces "buy sell" --strategy MyStrat.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .result import HyperoptResultError, load_result
from .selection import DEFAULT_EPOCH_FLOOR, EpochFloor, select_best_epoch
from .spaces import SpaceRequiresParamsError, normalize_spaces, validate_spaces_have_params


def _cmd_select(args) -> int:
    raw = load_result(args.result)
    floor = EpochFloor(min_trades=args.min_trades, min_profit_factor=args.min_profit_factor)
    sel = select_best_epoch(raw, floor)
    optimiser_pick = raw.get("best_epoch")

    if args.json:
        print(json.dumps({
            "epoch": sel.number,
            "optimiserPick": optimiser_pick,
            "overridden": bool(sel.number != optimiser_pick and not sel.degenerate),
            "eligible": sel.eligible,
            "considered": sel.considered,
            "degenerate": sel.degenerate,
            "params": (sel.epoch or {}).get("params_dict"),
            "metrics": (sel.epoch or {}).get("results_metrics"),
        }, indent=2, default=str))
        return 1 if sel.degenerate else 0

    print(f"Epochs read      {sel.considered}")
    print(f"Cleared floor    {sel.eligible}   (>= {floor.min_trades} trades, profit factor > {floor.min_profit_factor})")
    print()
    if sel.degenerate:
        print(f"NO epoch cleared the floor.")
        print(f"Freqtrade would hand you epoch {optimiser_pick}. Do not trade these parameters —")
        print("the search found nothing with enough evidence behind it.")
        return 1

    if sel.considered and sel.number != optimiser_pick:
        print(f"Freqtrade's pick   epoch {optimiser_pick}  (lowest loss, no trade-count constraint)")
        print(f"Guarded pick       epoch {sel.number}  (lowest loss AMONG epochs that clear the floor)")
    else:
        print(f"Winning epoch      {sel.number}   (freqtrade's own pick already clears the floor)")

    metrics = (sel.epoch or {}).get("results_metrics") or {}
    if metrics:
        keys = ("total_trades", "trade_count", "profit_total", "profit_factor", "sharpe")
        shown = [(k, metrics[k]) for k in keys if k in metrics]
        if shown:
            print()
            for k, v in shown:
                print(f"  {k:<16} {v}")
    params = (sel.epoch or {}).get("params_dict")
    if params and args.params:
        print()
        print(json.dumps(params, indent=2, default=str))
    return 0


def _cmd_check_spaces(args) -> int:
    code = Path(args.strategy).read_text()
    spaces = normalize_spaces(args.spaces)
    try:
        validate_spaces_have_params(spaces, code)
    except SpaceRequiresParamsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"ok — {', '.join(spaces)} can be optimised against {Path(args.strategy).name}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="freqtrade-hyperopt-guard",
        description="Stop a hyperopt run from handing you untradeable parameters.",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sel = sub.add_parser("select", help="re-pick the winning epoch under a quality floor")
    p_sel.add_argument("result", help="path to a .fthypt file")
    p_sel.add_argument("--min-trades", type=int, default=DEFAULT_EPOCH_FLOOR.min_trades,
                       help=f"minimum trades an epoch must show (default {DEFAULT_EPOCH_FLOOR.min_trades}; 0 disables)")
    p_sel.add_argument("--min-profit-factor", type=float, default=DEFAULT_EPOCH_FLOOR.min_profit_factor,
                       help=f"profit factor an epoch must EXCEED (default {DEFAULT_EPOCH_FLOOR.min_profit_factor}; 0 disables)")
    p_sel.add_argument("--params", action="store_true", help="also print the winning params_dict")
    p_sel.set_defaults(func=_cmd_select)

    p_sp = sub.add_parser("check-spaces", help="check a strategy declares the parameters a space needs")
    p_sp.add_argument("--spaces", nargs="+", required=True, help='e.g. --spaces buy sell  or  --spaces "buy sell"')
    p_sp.add_argument("--strategy", required=True, help="path to the strategy .py file")
    p_sp.set_defaults(func=_cmd_check_spaces)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (HyperoptResultError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
