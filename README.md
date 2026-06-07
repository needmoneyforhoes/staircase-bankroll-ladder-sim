# staircase-bankroll-ladder-sim

Staircase bankroll-laddering simulations for Polymarket: staged fire-size/cap tiers, $1-minimum variants, and HALT trade-off sweeps.

## Why it exists

The live 5-minute crypto bot starts from a small bankroll (e.g. $9) and needs to compound to a target (e.g. $100) without wiping out. This repo answers, offline: **for each bankroll stage, what fixed fire size / per-market cap / PAUSE / HALT floor maximizes the probability of reaching the next rung while keeping the wipe rate near zero?** It is a sizing-policy lab, not a trading bot — no orders are placed.

## How it works

Each script is a self-contained Monte Carlo over **replayed historical fire decisions**:

1. Parse `race_test_btc-updown-5m-*.log` replay files: extract every SHADOW/LIVE fire (`strategy`, `side`, `price`, `cd`) and the realized market winner. Fires with `cd <= 15` or price outside `(0,1)` are dropped.
2. Build the eligible strategy set = cheap-entry (`price <= $0.50`), positive-EV strategies with >= 20 samples.
3. Bootstrap-resample market sequences (seeded `random.Random(42)`) and walk a bankroll through them, applying per-stage **fire size**, **per-market cap**, **PAUSE** (stop firing below this balance), **HALT** floor (wipe), an **M1 probabilistic block** (loser/winner block rates), and a **DN-regime gate** (skip UP fires after 4+ of last 6 markets resolved DN). Report success %, wipe %, p50/p90 markets-to-target, and $/market.

| Script | Focus |
| --- | --- |
| `sim_staircase.py` | Original 4-stage ladder ($9→$20→$30→$50→$100); explores fire/cap/PAUSE/entry configs per stage, including sub-$1 fires. |
| `sim_staircase_v2.py` | Tightens the search to find a **95%+ success** config per stage; flags winners with `⭐`. |
| `sim_staircase_dollar_min.py` | Enforces the real **$1 fire minimum** (PM-bump constraint); PAUSE pinned to `HALT + cap×fire` for a no-wipe guarantee. |
| `sim_staircase_v3.py` | $1-min fires while **sweeping the HALT floor** ($5/$3/$2/$1) to expose the wipe-rate vs. speed trade-off; classifies runs as win/wipe/stuck. |

## Requirements

- Python 3.8+ — **standard library only** (`re`, `glob`, `random`, `collections`). No third-party deps, no virtualenv needed.
- No wallet, private key, or network access — these are pure offline simulations.
- Replay log data (see below).

## Usage

Run any variant directly; each prints its own tables to stdout (a couple of minutes each — 2000 runs × 2000-market bootstraps per config):

```bash
python3 sim_staircase.py            # full per-stage config exploration
python3 sim_staircase_v2.py         # hunt 95%+ configs (⭐ markers)
python3 sim_staircase_dollar_min.py # real $1-min fire, no-wipe PAUSE
python3 sim_staircase_v3.py         # $1-min, sweep HALT floor
```

## Data

These scripts read replay logs matching `race_test_btc-updown-5m-*.log`, expected at the hard-coded `PATH_PATTERN` (`/home/polybot/polymarket-bot/data/quant_bots_logs_replay/`). That directory is **not** part of this repo — it ships in the private `polymarket-data` repo. Point `PATH_PATTERN` at your local copy of those logs before running. With no logs present, the sims load 0 markets and produce empty tables.

> Private research software. No warranty; trades/handles real funds at your own risk.
