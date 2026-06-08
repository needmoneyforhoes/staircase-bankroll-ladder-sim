#!/usr/bin/env python3
"""sim_staircase_v2.py — find 95%+ success config per stage."""
import re, glob, random
from collections import defaultdict

PATH_PATTERN = './data/quant_bots_logs_replay/race_test_btc-updown-5m-*.log'
MIN_CD = 15
HALT_THRESH = 5.00
M1_BLOCK_LOSER = 0.58
M1_BLOCK_WINNER = 0.23


def load_markets():
    pattern = re.compile(
        r'(\d+)\.\s+(\S+)\s+(?:🔵 SHADOW|🟢 LIVE)\s+(UP|DN)\s+@\s+\$(\d+\.\d+)\s+[\d.]+sh\s+cd=(\d+)')
    winner_pattern = re.compile(r'MARKET RECAP.*\(winner=(\w+)\)')
    paths = sorted(set(glob.glob(PATH_PATTERN)))
    random.seed(42)
    if len(paths) > 500: paths = random.sample(paths, 500)
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
            fires.append({'strategy': strat, 'side': side, 'price': price,
                          'cd': cd, 'won': (side == winner)})
        if fires: markets[slug] = {'winner': winner, 'fires': fires}
    return markets


def compute_pos_ev(markets, max_entry=0.50):
    by_strat = defaultdict(list)
    for m in markets.values():
        for f in m['fires']:
            if f['price'] <= max_entry:
                by_strat[f['strategy']].append((f['price'], f['won']))
    ev = {}
    for s, items in by_strat.items():
        if len(items) < 20: continue
        e = sum((1/p - 1) if w else -1.0 for p, w in items) / len(items)
        if e > 0: ev[s] = (e, len(items))
    return ev


def simulate_stage(markets_data, slugs_seq, allowed, start, target,
                   fire_size, pause, cap, max_entry, max_mkts=2000, rng=None):
    if rng is None: rng = random
    bal = start
    mkts = 0
    recent = []
    for slug in slugs_seq[:max_mkts]:
        mkts += 1
        if bal >= target: return True, mkts
        if bal < HALT_THRESH: return False, mkts
        m = markets_data[slug]
        winner = m['winner']
        if bal < pause:
            recent.append(winner); continue
        dn6 = sum(1 for w in recent[-6:] if w == 'DN')
        skip_up = dn6 >= 4
        elig = [f for f in m['fires']
                if f['strategy'] in allowed and f['price'] <= max_entry
                and (not skip_up or f['side'] != 'UP')]
        if not elig: recent.append(winner); continue
        elig.sort(key=lambda f: f['price'])
        c = 0
        for f in elig:
            if c >= cap: break
            p_block = M1_BLOCK_LOSER if not f['won'] else M1_BLOCK_WINNER
            if rng.random() < p_block: continue
            if bal - fire_size < HALT_THRESH: continue
            c += 1
            if f['won']:
                bal += fire_size * (1.0 / f['price'] - 1)
            else:
                bal -= fire_size
            if bal >= target: return True, mkts
            if bal < HALT_THRESH: return False, mkts
        recent.append(winner)
    return bal >= target, mkts


def run_stage(markets, allowed, start, target, fs, pt, cap, me, n_runs=2000):
    slugs = list(markets.keys())
    rng = random.Random(42)
    results = []
    for _ in range(n_runs):
        seq = [rng.choice(slugs) for _ in range(2000)]
        success, mkts = simulate_stage(markets, seq, allowed, start, target,
                                       fs, pt, cap, me, 2000, rng)
        results.append((success, mkts))
    return results


def summarize(name, results, start, target):
    n = len(results)
    succ = sum(1 for s, _ in results if s)
    succ_mkts = sorted([m for s, m in results if s])
    if succ_mkts:
        nm = len(succ_mkts)
        p50 = succ_mkts[nm//2]
        usd_mkt = (target-start)/p50
        marker = '⭐' if succ/n >= 0.95 else ('  ')
        print(f"  {marker}{name:55s} succ={100*succ/n:5.1f}%  p50={p50:4d} mkts  ${usd_mkt:.2f}/mkt")
    else:
        print(f"  {name:55s} succ={100*succ/n:5.1f}%  NO SUCCESS")


def main():
    markets = load_markets()
    ALLOWED = set(compute_pos_ev(markets, max_entry=0.50))
    print(f"Loaded {len(markets)} mkts, {len(ALLOWED)} pos-EV cheap strategies\n")

    # STAGE 1: $9 → $20
    print("="*80)
    print("STAGE 1: $9 → $20  (looking for 95%+)")
    print("="*80)
    for fs, pt, cap in [(0.05, 5.05, 2), (0.10, 5.10, 1), (0.10, 5.10, 2),
                        (0.10, 5.10, 3), (0.15, 5.15, 2), (0.20, 5.20, 2),
                        (0.25, 5.25, 2)]:
        r = run_stage(markets, ALLOWED, 9.0, 20.0, fs, pt, cap, 0.50)
        summarize(f"fire=${fs:.2f} cap={cap} PAUSE=${pt:.2f}", r, 9.0, 20.0)

    # STAGE 2: $20 → $30
    print("\n" + "="*80)
    print("STAGE 2: $20 → $30  (looking for 95%+)")
    print("="*80)
    for fs, pt, cap in [(0.25, 5.25, 2), (0.30, 5.30, 2), (0.40, 5.40, 2),
                        (0.50, 5.50, 1), (0.50, 5.50, 2), (0.50, 5.50, 3)]:
        r = run_stage(markets, ALLOWED, 20.0, 30.0, fs, pt, cap, 0.50)
        summarize(f"fire=${fs:.2f} cap={cap}", r, 20.0, 30.0)

    # STAGE 3: $30 → $50
    print("\n" + "="*80)
    print("STAGE 3: $30 → $50  (looking for 95%+)")
    print("="*80)
    for fs, pt, cap in [(0.50, 5.50, 2), (0.75, 5.75, 2), (1.00, 6.00, 2),
                        (1.00, 6.00, 3), (1.50, 6.50, 2)]:
        r = run_stage(markets, ALLOWED, 30.0, 50.0, fs, pt, cap, 0.50)
        summarize(f"fire=${fs:.2f} cap={cap}", r, 30.0, 50.0)

    # STAGE 4: $50 → $100
    print("\n" + "="*80)
    print("STAGE 4: $50 → $100  (looking for 95%+)")
    print("="*80)
    for fs, pt, cap in [(1.00, 6.00, 3), (1.50, 6.50, 3), (2.00, 7.00, 3),
                        (2.50, 7.50, 3), (3.00, 8.00, 3)]:
        r = run_stage(markets, ALLOWED, 50.0, 100.0, fs, pt, cap, 0.50)
        summarize(f"fire=${fs:.2f} cap={cap}", r, 50.0, 100.0)


if __name__ == "__main__":
    main()
