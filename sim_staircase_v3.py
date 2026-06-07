#!/usr/bin/env python3
"""sim_staircase_v3.py — $1 min fire, vary HALT to find best trade-off."""
import re, glob, random
from collections import defaultdict

PATH = '/home/polybot/polymarket-bot/data/quant_bots_logs_replay/race_test_btc-updown-5m-*.log'
MIN_CD = 15
M1_BL = 0.58
M1_BW = 0.23


def load():
    pat = re.compile(r'(\d+)\.\s+(\S+)\s+(?:🔵 SHADOW|🟢 LIVE)\s+(UP|DN)\s+@\s+\$(\d+\.\d+)\s+[\d.]+sh\s+cd=(\d+)')
    wp = re.compile(r'MARKET RECAP.*\(winner=(\w+)\)')
    paths = sorted(set(glob.glob(PATH))); random.seed(42)
    if len(paths) > 500: paths = random.sample(paths, 500)
    M = {}
    for p in paths:
        try: t = open(p).read()
        except: continue
        m = wp.search(t)
        if not m: continue
        w = m.group(1)
        if w not in ('UP','DN'): continue
        slug = p.split('-')[-1].replace('.log','')
        fires = []
        for fm in pat.finditer(t):
            try:
                s = fm.group(2); sd = fm.group(3); pr = float(fm.group(4)); cd = int(fm.group(5))
            except: continue
            if pr<=0 or pr>=1 or cd<=MIN_CD: continue
            fires.append({'strategy':s,'side':sd,'price':pr,'won':(sd==w)})
        if fires: M[slug] = {'winner':w, 'fires':fires}
    return M


def compute_ev(M, me=0.50):
    by = defaultdict(list)
    for m in M.values():
        for f in m['fires']:
            if f['price'] <= me: by[f['strategy']].append((f['price'],f['won']))
    ev = {}
    for s,it in by.items():
        if len(it) < 20: continue
        e = sum((1/p-1) if w else -1.0 for p,w in it)/len(it)
        if e > 0: ev[s] = e
    return set(ev)


def sim_stage(M, seq, allowed, start, target, fs, pause, cap, me, halt, max_m=2000, rng=None):
    if rng is None: rng = random
    bal = start; mkts = 0; rec = []; wipes = 0; stuck = 0
    for slug in seq[:max_m]:
        mkts += 1
        if bal >= target: return ('win', mkts, bal)
        if bal <= halt: return ('wipe', mkts, bal)
        m = M[slug]; w = m['winner']
        if bal < pause: rec.append(w); continue
        dn6 = sum(1 for x in rec[-6:] if x=='DN')
        skip_up = dn6 >= 4
        elig = [f for f in m['fires'] if f['strategy'] in allowed and f['price']<=me and (not skip_up or f['side']!='UP')]
        if not elig: rec.append(w); continue
        elig.sort(key=lambda f: f['price'])
        c = 0
        for f in elig:
            if c >= cap: break
            p_blk = M1_BL if not f['won'] else M1_BW
            if rng.random() < p_blk: continue
            if bal - fs <= halt: continue
            c += 1
            if f['won']: bal += fs * (1.0/f['price'] - 1)
            else: bal -= fs
            if bal >= target: return ('win', mkts, bal)
            if bal <= halt: return ('wipe', mkts, bal)
        rec.append(w)
    return ('stuck', mkts, bal)


def run(M, allowed, start, target, fs, cap, pause, me, halt, n=2000):
    slugs = list(M.keys()); rng = random.Random(42); res = []
    for _ in range(n):
        sq = [rng.choice(slugs) for _ in range(2000)]
        res.append(sim_stage(M, sq, allowed, start, target, fs, pause, cap, me, halt, 2000, rng))
    return res


def summ(name, res):
    n = len(res)
    won = sum(1 for r,_,_ in res if r=='win')
    wip = sum(1 for r,_,_ in res if r=='wipe')
    stk = sum(1 for r,_,_ in res if r=='stuck')
    won_m = sorted([m for r,m,_ in res if r=='win'])
    p50 = won_m[len(won_m)//2] if won_m else 0
    p90 = won_m[9*len(won_m)//10] if won_m else 0
    mk = '⭐' if won/n>=0.95 else ('🟢' if won/n>=0.80 else ('🟡' if won/n>=0.50 else '  '))
    print(f"  {mk}{name:55s} won={100*won/n:5.1f}% wipe={100*wip/n:4.1f}% stuck={100*stk/n:4.1f}% p50={p50:4d} p90={p90:4d}")


def main():
    M = load()
    A = compute_ev(M, 0.50)
    print(f"Loaded {len(M)} mkts, {len(A)} pos-EV cheap strategies\n")

    for halt in [5.0, 3.0, 2.0, 1.0]:
        print(f"\n{'='*80}\n  HALT=${halt:.2f}  STAGE 1: $9 → $20\n{'='*80}")
        cfgs = [
            (1.00, 1, max(halt+1.0, halt+1.0)),  # PAUSE = HALT + cap*fire
            (1.00, 2, halt+2.0),
            (1.00, 3, halt+3.0),
        ]
        for fs, cap, pt in cfgs:
            r = run(M, A, 9.0, 20.0, fs, cap, pt, 0.50, halt)
            summ(f"fire=${fs:.2f}×{cap} PAUSE=${pt:.2f}", r)


if __name__ == "__main__":
    main()
