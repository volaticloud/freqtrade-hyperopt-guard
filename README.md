# freqtrade-hyperopt-guard

Stop a hyperopt run from handing you untradeable parameters.

Freqtrade's hyperopt loss functions carry **no minimum-trade-count constraint**.
The optimiser minimises loss and nothing else — so a search that stumbles on
parameters entering twice in ten months and winning both times scores a superb
Sharpe on a sample of two, and *that* is returned as the best epoch, with nothing
marking it as untradeable.

```console
$ freqtrade-hyperopt-guard select user_data/hyperopt_results/MyStrat.fthypt
Epochs read      100
Cleared floor    31   (>= 50 trades, profit factor > 1.0)

Freqtrade's pick   epoch 63  (lowest loss, no trade-count constraint)
Guarded pick       epoch 12  (lowest loss AMONG epochs that clear the floor)

  total_trades     184
  profit_total     0.0234
  profit_factor    1.61
  sharpe           2.44
```

Reads Freqtrade's own `.fthypt` file. No conversion step.

## Install

```bash
pip install freqtrade-hyperopt-guard
```

No dependencies. Python 3.9+.

## The two guards

### After the run — re-pick the winner

The optimiser's choice is treated as an **input, not the authority**. Freqtrade
ships every evaluated epoch in the `.fthypt`, so the winner is re-selected from
the full set subject to a floor. Among epochs that clear it, the same rule the
optimiser uses applies — lowest loss wins, earliest breaks a tie — so a run whose
best epoch is already tradeable comes back unchanged.

When **nothing** clears the floor you get a non-zero exit and a plain statement:

```console
$ freqtrade-hyperopt-guard select thin-run.fthypt
Epochs read      100
Cleared floor    0   (>= 50 trades, profit factor > 1.0)

NO epoch cleared the floor.
Freqtrade would hand you epoch 63. Do not trade these parameters —
the search found nothing with enough evidence behind it.
```

That case is the whole point. Reporting the least-bad untradeable epoch as "the
best parameters" without saying so is the defect.

The floor is a **parameter, not a constant**, because the right threshold depends
on timeframe and window — 50 trades is thin for a 5m strategy over a year and
unreachable for a 1d strategy over a month:

```bash
freqtrade-hyperopt-guard select run.fthypt --min-trades 100 --min-profit-factor 1.2
freqtrade-hyperopt-guard select run.fthypt --min-trades 0      # disable that test
```

### Before the run — check the spaces can work

Freqtrade accepts `--spaces buy` against a strategy declaring no optimizable
parameters, then fails deep in the engine with *"The 'buy' space is included in
the hyperoptimization but no parameter(s) to optimize were found"*. That is a
wasted setup, and on a long run a wasted queue slot.

```bash
freqtrade-hyperopt-guard check-spaces --spaces "buy sell" --strategy MyStrat.py
```

`roi`, `stoploss` and `trailing` are never blocked — freqtrade has built-in
ranges for those and they need no declared parameters. The aggregates `default`
and `all` are expanded and checked for what they imply.

## As a library

```python
from freqtrade_hyperopt_guard import EpochFloor, load_result, select_best_epoch

sel = select_best_epoch(
    load_result("user_data/hyperopt_results/MyStrat.fthypt"),
    EpochFloor(min_trades=100, min_profit_factor=1.2),
)

if sel.degenerate:
    raise SystemExit("no epoch cleared the floor")

print(sel.number, sel.epoch["params_dict"])
```

## How the floor works

| Test | Default | Rule |
|---|---:|---|
| Trade count | 50 | Epoch must report **at least** this many trades. `0` disables. |
| Profit factor | 1.0 | Epoch must **exceed** this — equalling it is not enough. `0` disables. |

**A missing or non-finite profit factor is treated as absent, not as a failure.**
Freqtrade emits `Infinity` for an epoch with zero losing trades, and some
pipelines drop the field entirely; rejecting those would discard the best epochs
of a strongly trending run. The trade count is then the only evidence — which is
why a thin epoch with no profit factor is still rejected. An infinite profit
factor never rescues a 2-trade epoch.

## What this is not

It does not make a strategy good, and a cleared floor is not permission to go
live. It answers one narrow question: *is there enough evidence behind these
parameters to be worth acting on?* Everything else that makes backtests
misleading — look-ahead bias, survivorship bias in the pair list, optimistic
fills, a regime that doesn't repeat — is invisible to it.

Once you have parameters worth trusting, the next question is whether they
survive data the optimiser never saw. That's
[freqtrade-overfit-score](https://github.com/volaticloud/freqtrade-overfit-score).

Trading involves risk of loss. Nothing here is financial advice.

## Accuracy

The same selection rule runs in Go inside [VolatiCloud](https://volaticloud.com).
Both implementations are pinned to the golden vectors in
`tests/testdata/selection_vectors.json`, so this package picks the same epoch the
platform would for identical input. A disagreement is a bug worth reporting.

One case the shared vectors *cannot* cover: freqtrade writes bare `Infinity` into
`.fthypt`, which Python reads as `float('inf')` but Go's JSON parser rejects
outright. That branch is asserted separately on both sides.

## Releasing

Publishing uses PyPI Trusted Publishing, so no API token is stored here. Bump
`version` in `pyproject.toml`, tag it, cut a GitHub Release — the workflow
refuses a tag that disagrees with `pyproject.toml` and runs the vectors first.

## About

Built and maintained by [VolatiCloud](https://volaticloud.com), a managed
Freqtrade platform. We run a lot of hyperopts and this guard is the rule we
apply to all of them.

Self-hosting Freqtrade is great, and this tool is for you whether or not you ever
use anything of ours. It makes no network calls and collects nothing.

**Not affiliated with or endorsed by the Freqtrade project.** Freqtrade is an
independent open-source project; this is a third-party tool that reads its output.

## License

MIT — see [LICENSE](LICENSE).
