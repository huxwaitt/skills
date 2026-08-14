#!/usr/bin/env python3
"""
vev.py — Vector EV decision engine for the advise-vev skill.

Does the arithmetic that's tedious and error-prone by hand: rank -> ROC weights,
raw outcomes -> 0-100 value scores (with benefit/cost direction), the weighted-additive
collapse, and a weight-sensitivity check. Keeps the value VECTOR visible alongside the
single scalar pick.

Grounded in Edwards & Barron (1994) SMARTER + ROC weights (Barron 1992; robustness
Barron & Barrett 1996). See references/roc-weights.md for the spec and golden numbers.

USAGE
-----
Write a JSON spec describing the decision and pass its path:

    python vev.py decision.json

Spec format:
{
  "units": [
    {"name": "Money",    "rank": 1, "direction": "benefit"},
    {"name": "Happiness","rank": 2, "direction": "benefit"},
    {"name": "FreeTime", "rank": 3, "direction": "benefit"}
  ],
  "options": [
    {"name": "Job A", "raw": {"Money": 90000, "Happiness": 40, "FreeTime": 10}},
    {"name": "Job B", "raw": {"Money": 60000, "Happiness": 90, "FreeTime": 95}}
  ],
  "weight_method": "ROC"     // optional: ROC (default) | RS | equal
}

- rank: 1 = matters most. Ties not allowed (force a strict order; that's the method).
- direction: "benefit" (more is better) or "cost" (less is better).
- raw values may be numbers (any scale) OR already-scored 0-100 for qualitative units
  (use direction "benefit" and put 0-100 numbers in; scaling is a no-op if range fits 0-100).

Prints a full report: ROC weights, the value VECTOR (per-unit 0-100 table), the scalar
ranking, the winner, and a sensitivity note (does the winner survive adjacent rank swaps?).

It computes; it does not decide for the user about values. No network, no side effects.
"""

import json
import sys
from itertools import permutations


# ---------- weights ----------

def roc_weights(n):
    """Rank-Order Centroid weights for n ranked items. w_k = (1/n) * sum_{i=k}^{n} 1/i."""
    return [sum(1.0 / i for i in range(k, n + 1)) / n for k in range(1, n + 1)]


def rs_weights(n):
    """Rank-Sum weights (flatter alternative). w_r = (n - r + 1) / (n(n+1)/2)."""
    denom = n * (n + 1) / 2.0
    return [(n - r + 1) / denom for r in range(1, n + 1)]


def equal_weights(n):
    return [1.0 / n] * n


WEIGHT_FNS = {"ROC": roc_weights, "RS": rs_weights, "equal": equal_weights}


# ---------- scoring ----------

def score_unit(raw_values, direction):
    """Map raw outcomes for one unit to 0-100 via local linear scaling.
    benefit: best raw -> 100, worst raw -> 0.  cost: flips.
    If all options tie on this unit (zero range), everyone gets 50 (it doesn't
    discriminate, so it shouldn't swing the result)."""
    lo, hi = min(raw_values), max(raw_values)
    if hi == lo:
        return [50.0] * len(raw_values)
    out = []
    for x in raw_values:
        if direction == "cost":
            out.append(100.0 * (hi - x) / (hi - lo))
        else:
            out.append(100.0 * (x - lo) / (hi - lo))
    return out


# ---------- core ----------

def build(spec):
    units = sorted(spec["units"], key=lambda u: u["rank"])
    names = [u["name"] for u in units]
    n = len(units)
    method = spec.get("weight_method", "ROC")
    weights = WEIGHT_FNS[method](n)

    opts = spec["options"]
    # per-unit 0-100 score vectors
    vectors = {}  # unit -> [score per option]
    for u in units:
        raw = [o["raw"][u["name"]] for o in opts]
        vectors[u["name"]] = score_unit(raw, u.get("direction", "benefit"))

    # scalar value per option
    scalars = []
    for oi, o in enumerate(opts):
        v = sum(weights[ui] * vectors[u["name"]][oi] for ui, u in enumerate(units))
        scalars.append(v)

    return units, names, weights, opts, vectors, scalars, method


def sensitivity(spec, units, opts, baseline_winner_idx):
    """Does the winner survive every ADJACENT rank swap? Cheap robustness probe in the
    spirit of Belton & Stewart: don't trust one ranking — see if small defensible
    changes flip it. Returns list of (swap_desc, new_winner_name) that CHANGE the winner."""
    flips = []
    ordered = sorted(units, key=lambda u: u["rank"])
    n = len(ordered)
    for i in range(n - 1):
        swapped = [dict(u) for u in ordered]
        swapped[i]["rank"], swapped[i + 1]["rank"] = swapped[i + 1]["rank"], swapped[i]["rank"]
        s2 = dict(spec)
        s2["units"] = swapped
        _, _, _, opts2, _, scalars2, _ = build(s2)
        w_idx = max(range(len(scalars2)), key=lambda k: scalars2[k])
        if w_idx != baseline_winner_idx:
            flips.append((f"{ordered[i]['name']} <-> {ordered[i+1]['name']}", opts2[w_idx]["name"]))
    return flips


def report(spec):
    units, names, weights, opts, vectors, scalars, method = build(spec)
    order = sorted(range(len(opts)), key=lambda k: scalars[k], reverse=True)
    winner_idx = order[0]

    lines = []
    lines.append(f"WEIGHTS ({method}, rank 1 = matters most):")
    for u, w in zip(units, weights):
        lines.append(f"  {u['name']:<16} rank {u['rank']}  ->  {w:.3f}")
    lines.append(f"  (sum = {sum(weights):.3f})")
    lines.append("")

    def bar(v):
        # 10-cell bar; filled by score/10. Shows shape at a glance.
        filled = int(round(v / 10.0))
        return "█" * filled + "·" * (10 - filled)

    lines.append("VALUE VECTOR (each unit 0-100, bar = how good; ★ = best in column):")
    name_w = max(12, *(len(o["name"]) for o in opts))
    # per-unit, which option is best (for the star marker)
    best_in_col = {u["name"]: max(range(len(opts)), key=lambda k: vectors[u["name"]][k]) for u in units}
    for u in units:
        # one block per unit: easier to read than a wide grid
        lines.append(f"  {u['name']}  (rank {u['rank']}, weight {weights[units.index(u)]:.2f})")
        for oi in order:
            v = vectors[u["name"]][oi]
            star = " ★" if best_in_col[u["name"]] == oi else "  "
            mark = " <- PICK" if oi == winner_idx else ""
            lines.append(f"    {opts[oi]['name']:<{name_w}}  {bar(v)} {v:5.1f}{star}")
        lines.append("")

    lines.append("OVERALL (weighted total, 0-100):")
    smax = max(scalars) or 1
    for oi in order:
        v = scalars[oi]
        b = "█" * int(round(v / smax * 20)) + "·" * (20 - int(round(v / smax * 20)))
        mark = "  <- PICK" if oi == winner_idx else ""
        lines.append(f"  {opts[oi]['name']:<{name_w}}  {b} {v:5.1f}{mark}")
    lines.append("")

    lines.append(f"PICK: {opts[winner_idx]['name']}  (scalar {scalars[winner_idx]:.1f})")
    # where it wins / loses
    best_unit = max(units, key=lambda u: vectors[u["name"]][winner_idx])
    worst_unit = min(units, key=lambda u: vectors[u["name"]][winner_idx])
    lines.append(f"  strongest on: {best_unit['name']}   weakest on: {worst_unit['name']}")
    lines.append("")

    flips = sensitivity(spec, units, opts, winner_idx)
    if not flips:
        lines.append("SENSITIVITY: winner holds under all adjacent rank swaps. Robust pick.")
    else:
        lines.append("SENSITIVITY: winner is FRAGILE — these adjacent swaps change it:")
        for desc, new_w in flips:
            lines.append(f"  if {desc}  ->  {new_w} wins instead")
        lines.append("  (the decision hinges on these rankings; worth the user's attention)")

    return "\n".join(lines)


def main():
    # The report draws with ★ █ ·; Windows consoles default to cp1252 and would
    # raise UnicodeEncodeError on them.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:  # pre-3.7 stdout, or already-wrapped stream
        pass
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    with open(sys.argv[1], encoding="utf-8") as f:
        spec = json.load(f)
    print(report(spec))


if __name__ == "__main__":
    main()
