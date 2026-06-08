#!/usr/bin/env python3
"""sim_staircase.py — staircase strategy: $9 → $20 → $30 → ... → $100.

Each stage uses fire size/cap optimized for THAT stage's risk/reward profile.
Goal: 95%+ success on EACH stage, fast.

Stage 1: $9 → $20    (+122%)  — most variance, use small fires
Stage 2: $20 → $30   (+50%)
Stage 3: $30 → $50   (+67%)
Stage 4: $50 → $100  (+100%)
"""
import re
import glob
import random
from collections import defaultdict


PATH_PATTERN = './data/quant_bots_logs_replay/race_test_btc-updown-5m-*.log'
MIN_CD = 15
HALT_THRESH = 5.00

M1_BLOCK_LOSER  = 0.58
M1_BLOCK_WINNER = 0.23


def load_markets():
    pattern = re.compile(
        r'(\d+)\.\s+(\S+)\s+(?:🔵 SHADOW|🟢 LIVE)\s+(UP|DN)\s+@\s+\$(\d+\.\d+)\s+[\d.]+sh\s+cd=(\d+)')
    winner_pattern = re.compile(r'MARKET RECAP.*\(winner=(\w+)\)')

    paths = sorted(set(glob.glob(PATH_PATTERN)))
    random.seed(42)
    if len(paths) > 500:
        paths = random.sample(paths, 500)

    markets = {}
    for p in paths:
        try: text = open(p).read()
        except: continue
        m = winner_pattern.search(text)
        if not m: continue
        winner = m.group(1)
        if winner not in ('UP', 'DN'): continue
        slug = p.split('-')[-1].replace('.log', '')
        fires = []
        for fm in pattern.finditer(text):
            try:
                strat = fm.group(2); side = fm.group(3)
                price = float(fm.group(4)); cd = int(fm.group(5))
            except: continue
            if price <= 0 or price >= 1 or cd <= MIN_CD: continue
            won = (side == winner)
            fires.append({'strategy': strat, 'side': side, 'price': price,
                          'cd': cd, 'won': won})
        if fires:
            markets[slug] = {'winner': winner, 'fires': fires}
    return markets


def compute_strategy_ev(markets, max_entry=1.0):
    by_strat = defaultdict(list)
    for m in markets.values():
        for f in m['fires']:
            if f['price'] <= max_entry:
                by_strat[f['strategy']].append((f['price'], f['won']))
    ev_table = {}
    for s, items in by_strat.items():
        if len(items) < 20: continue
        ev = sum((1/p - 1) if w else -1.0 for p, w in items) / len(items)
        ev_table[s] = (ev, len(items))
    return ev_table


def simulate_stage(markets_data, slugs_seq, allowed, start_bal, target_bal,
                   fire_size, pause_thresh, cap, max_entry, m1_on=True,
                   regime_on=True, max_mkts=2000, rng=None):
    """Simulate one stage. Returns success bool + markets used."""
    if rng is None: rng = random
    bal = start_bal
    mkts_used = 0
    fires = 0
    recent_winners = []

    for slug in slugs_seq[:max_mkts]:
        mkts_used += 1
        m = markets_data[slug]
        winner = m['winner']
        if bal >= target_bal:
            return True, mkts_used, fires
        if bal < HALT_THRESH:
            return False, mkts_used, fires  # wiped
        if bal < pause_thresh:
            recent_winners.append(winner)
            continue

        # Regime gate
        dn6 = sum(1 for w in recent_winners[-6:] if w == 'DN')
        skip_up = regime_on and dn6 >= 4

        elig = [f for f in m['fires']
                if f['strategy'] in allowed and f['price'] <= max_entry
                and (not skip_up or f['side'] != 'UP')]
        if not elig:
            recent_winners.append(winner)
            continue
        elig.sort(key=lambda f: f['price'])
        taken_count = 0
        for f in elig:
            if taken_count >= cap: break
            if m1_on:
                p_block = M1_BLOCK_LOSER if not f['won'] else M1_BLOCK_WINNER
                if rng.random() < p_block:
                    continue
            if bal - fire_size < HALT_THRESH:
                continue
            fires += 1
            taken_count += 1
            if f['won']:
                bal += fire_size * (1.0 / f['price'] - 1)
            else:
                bal -= fire_size
            if bal >= target_bal:
                return True, mkts_used, fires
            if bal < HALT_THRESH:
                return False, mkts_used, fires
        recent_winners.append(winner)
    return (bal >= target_bal, mkts_used, fires)


def run_stage(markets_data, allowed, start_bal, target_bal, fire_size,
              pause_thresh, cap, max_entry, n_runs=2000, budget=2000):
    slugs = list(markets_data.keys())
    rng = random.Random(42)
    results = []
    for _ in range(n_runs):
        seq = [rng.choice(slugs) for _ in range(budget)]
        success, mkts, fires = simulate_stage(markets_data, seq, allowed,
                                              start_bal, target_bal, fire_size,
                                              pause_thresh, cap, max_entry,
                                              max_mkts=budget, rng=rng)
        results.append({'success': success, 'mkts': mkts, 'fires': fires})
    return results


def summarize_stage(name, results, start_bal, target_bal):
    n = len(results)
    succ = sum(1 for r in results if r['success'])
    mkts_succ = sorted([r['mkts'] for r in results if r['success']])
    print(f"\n  {name}")
    print(f"    success: {succ:5d}/{n} ({100*succ/n:.1f}%)")
    if mkts_succ:
        nm = len(mkts_succ)
        m_p25 = mkts_succ[nm//4]
        m_p50 = mkts_succ[nm//2]
        m_p90 = mkts_succ[9*nm//10]
        usd_per_mkt = (target_bal - start_bal) / m_p50
        print(f"    mkts: p25={m_p25} p50={m_p50} p90={m_p90}")
        print(f"    $/mkt at p50: ${usd_per_mkt:.3f}")


def main():
    markets = load_markets()
    print(f"Loaded {len(markets)} markets")
    ev_50 = compute_strategy_ev(markets, max_entry=0.50)
    ALLOWED = {s for s, (ev, n) in ev_50.items() if ev > 0 and n >= 20}
    print(f"  {len(ALLOWED)} cheap-entry positive-EV strategies\n")

    print("="*80)
    print("STAGE 1: $9 → $20  — explore best config")
    print("="*80)
    stage1_configs = [
        ('fire=$0.25 PAUSE=$5.25 cap=1 entry≤$0.50', 0.25, 5.25, 1, 0.50),
        ('fire=$0.25 PAUSE=$5.25 cap=2 entry≤$0.50', 0.25, 5.25, 2, 0.50),
        ('fire=$0.50 PAUSE=$5.50 cap=1 entry≤$0.50', 0.50, 5.50, 1, 0.50),
        ('fire=$0.50 PAUSE=$5.50 cap=2 entry≤$0.50', 0.50, 5.50, 2, 0.50),
        ('fire=$0.50 PAUSE=$5.50 cap=1 entry≤$0.30', 0.50, 5.50, 1, 0.30),
        ('fire=$1.00 PAUSE=$6.00 cap=1 entry≤$0.50', 1.00, 6.00, 1, 0.50),
        ('fire=$0.10 PAUSE=$5.10 cap=2 entry≤$0.50 (tiny+safe)', 0.10, 5.10, 2, 0.50),
        ('fire=$0.10 PAUSE=$5.10 cap=3 entry≤$0.50', 0.10, 5.10, 3, 0.50),
    ]
    for name, fs, pt, cap, me in stage1_configs:
        r = run_stage(markets, ALLOWED, 9.0, 20.0, fs, pt, cap, me, n_runs=2000)
        summarize_stage(name, r, 9.0, 20.0)

    print("\n" + "="*80)
    print("STAGE 2: $20 → $30  — bigger margin from floor, can be more aggressive")
    print("="*80)
    stage2_configs = [
        ('fire=$0.50 cap=2 entry≤$0.50', 0.50, 5.50, 2, 0.50),
        ('fire=$1.00 cap=2 entry≤$0.50', 1.00, 6.00, 2, 0.50),
        ('fire=$1.00 cap=3 entry≤$0.50', 1.00, 6.00, 3, 0.50),
        ('fire=$2.00 cap=2 entry≤$0.50', 2.00, 7.00, 2, 0.50),
    ]
    for name, fs, pt, cap, me in stage2_configs:
        r = run_stage(markets, ALLOWED, 20.0, 30.0, fs, pt, cap, me, n_runs=2000)
        summarize_stage(name, r, 20.0, 30.0)

    print("\n" + "="*80)
    print("STAGE 3: $30 → $50  — even more aggressive")
    print("="*80)
    stage3_configs = [
        ('fire=$1.00 cap=3 entry≤$0.50', 1.00, 6.00, 3, 0.50),
        ('fire=$2.00 cap=3 entry≤$0.50', 2.00, 7.00, 3, 0.50),
        ('fire=$3.00 cap=2 entry≤$0.50', 3.00, 8.00, 2, 0.50),
    ]
    for name, fs, pt, cap, me in stage3_configs:
        r = run_stage(markets, ALLOWED, 30.0, 50.0, fs, pt, cap, me, n_runs=2000)
        summarize_stage(name, r, 30.0, 50.0)

    print("\n" + "="*80)
    print("STAGE 4: $50 → $100  — compound mode")
    print("="*80)
    stage4_configs = [
        ('fire=$2.00 cap=3 entry≤$0.50', 2.00, 7.00, 3, 0.50),
        ('fire=$5.00 cap=2 entry≤$0.50', 5.00, 10.00, 2, 0.50),
        ('fire=$5.00 cap=3 entry≤$0.50', 5.00, 10.00, 3, 0.50),
    ]
    for name, fs, pt, cap, me in stage4_configs:
        r = run_stage(markets, ALLOWED, 50.0, 100.0, fs, pt, cap, me, n_runs=2000)
        summarize_stage(name, r, 50.0, 100.0)


if __name__ == "__main__":
    main()
