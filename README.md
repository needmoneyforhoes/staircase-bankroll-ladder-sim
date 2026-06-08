# staircase-bankroll-ladder-sim

Monte Carlo sims that search per-stage fire-size, per-market cap, PAUSE, and HALT settings for compounding a small Polymarket bankroll up a fixed ladder ($9 to $100). Sizing-policy lab, no orders are placed.

Each script replays historical fire decisions and bootstraps market sequences:

1. Parse `race_test_btc-updown-5m-*.log` files: extract each SHADOW/LIVE fire (`strategy`, `side`, `price`, `cd`) and the realized winner. Drop fires with `cd <= 15` or price outside `(0,1)`. Cap input at 500 logs (seeded `random.seed(42)`).
2. Eligible set = cheap-entry (`price <= 0.50`), positive-EV strategies with >= 20 samples.
3. Bootstrap 2000 market sequences (seeded `random.Random(42)`), walk a bankroll through 2000 markets each, applying fire size, per-market cap, PAUSE (stop firing below this balance), HALT floor (wipe), an M1 probabilistic block (loser 0.58 / winner 0.23), and a DN-regime gate (skip UP fires when 4+ of last 6 winners are DN).

Output: success %, wipe %, p50/p90 markets-to-target, and $/market per config.

## Scripts

- `sim_staircase.py`: 4-stage ladder ($9/$20/$30/$50/$100). Explores fire/cap/PAUSE/entry per stage, including sub-$1 fires.
- `sim_staircase_v2.py`: narrower search for 95%+ success per stage. Flags hits with a star marker.
- `sim_staircase_dollar_min.py`: enforces the $1 fire minimum. PAUSE pinned to `HALT + cap*fire` for a no-wipe guarantee.
- `sim_staircase_v3.py`: $1-min fires, sweeps the HALT floor ($5/$3/$2/$1). Classifies each run win/wipe/stuck.

## Usage

Each script prints its own tables to stdout. A couple of minutes each (2000 runs x 2000-market bootstraps per config).

```bash
python3 sim_staircase.py
python3 sim_staircase_v2.py
python3 sim_staircase_dollar_min.py
python3 sim_staircase_v3.py
```

## Data

Reads `race_test_btc-updown-5m-*.log` from `$DATA_DIR` (set the `PATH_PATTERN` constant in each script). Logs ship in the private polymarket-data repo, not here. With no logs present the sims load 0 markets and print empty tables.

Python 3.8+, standard library only. No wallet, key, or network access.
