# ROC weights — the rank-to-weight math

This is the engine of `advise-vev`. The user ranks the value-units; this turns that ranking into
weights. Read this when you need to compute weights or explain where they came from.

Source: Edwards & Barron (1994), SMARTS/SMARTER; ROC originates with Barron (1992); robustness from
Barron & Barrett (1996). Use the bundled `scripts/vev.py` to compute — don't do the arithmetic by
hand, it's error-prone. This file is the spec the script implements, plus the golden numbers.

## Why rank-then-convert (the whole reason this method exists)

Edwards & Barron built SMARTER because asking people for **precise numeric weights** ("money is
2.3x as important as time") is a false-precision trap: the answer depends heavily on the
elicitation method, people aren't consistent, and the "true" weights are unknowable anyway. People
*are* reliable and confident about **rank order** ("money matters more than time"). So: elicit only
the ranking, then convert ranks to weights with a formula that provably minimizes the worst-case
error in the unknown true weights.

The payoff is empirical, not just tidy: ROC weights pick the **same top option as a full
true-weight model in ~85% of cases**, and when they miss, the average value lost is small (Barron &
Barrett 1996; Katsikopoulos & Fasolo 2006). SMARTER lands ~98% as well as the heavier SMARTS that
demands numeric weights. That is the "good enough, with far less burden" bargain — and it's exactly
why `advise-vev` never makes the user assign points.

## The ROC formula

Rank the N value-units 1..N, where **rank 1 = matters most**. The weight for the unit at rank k:

```
w_k = (1/N) * sum_{i=k}^{N} (1/i)
       = (1/N) * ( 1/k + 1/(k+1) + ... + 1/N )
```

Properties (free, no extra steps): all weights >= 0, strictly decreasing in rank, and they
**sum to exactly 1**. No normalization needed.

It's called "centroid" because the weights are the center of mass of the simplex of all weight
vectors consistent with the ranking — the min-max-error point. (Derivation detail in methods.md;
you rarely need it to use the method.)

## Golden weight vectors (use these to sanity-check the script)

Computed directly from the formula, rounded to 3 dp. These are verified against multiple published
tables (Roszkowska 2013; TRB TCRP-131; Hatefi 2022).

```
N=2:  0.750, 0.250
N=3:  0.611, 0.278, 0.111
N=4:  0.521, 0.271, 0.146, 0.063
N=5:  0.457, 0.257, 0.157, 0.090, 0.040
N=6:  0.408, 0.242, 0.158, 0.103, 0.061, 0.028
N=7:  0.370, 0.228, 0.156, 0.109, 0.073, 0.044, 0.020
```

Each row sums to 1.000 (subject to rounding). The script computes the formula exactly and rounds
only for display — published tables vary in the last digit (half-up vs half-even), so a +/-0.001
difference on a tail weight is rounding convention, not an error. What must always hold: weights
strictly decrease and sum to exactly 1.

## Worked end-to-end example (N=3)

Units ranked: Money (#1), Happiness (#2), Free time (#3) -> ROC weights 0.611, 0.278, 0.111.
Scores (0-100, where 100 = best level present among the options):

```
              Money(0.611)  Happiness(0.278)  FreeTime(0.111)
Job A             100             40                10
Job B              25             90               100
```

```
V(Job A) = 0.611*100 + 0.278*40 + 0.111*10  = 61.1 + 11.1 + 1.1  = 73.3
V(Job B) = 0.611*25  + 0.278*90 + 0.111*100 = 15.3 + 25.0 + 11.1 = 51.4
```

-> Job A wins. Note *where* it wins: money. If money and happiness swapped ranks, recompute —
that's the sensitivity check (see vector-ev.md).

## Scoring each option on each unit (the value functions)

Convert raw outcomes to a 0-100 value scale, **per unit**, using the range actually spanned by the
options (local scaling — this is what makes the weights mean something, see methods.md on swing
weights):

- Benefit unit (more is better): `v = 100 * (x - x_worst) / (x_best - x_worst)`
- Cost unit (less is better):     `v = 100 * (x_best - x) / (x_best - x_worst)`

where x_worst / x_best are the worst / best raw levels among the options on that unit. Default to
**linear** (Edwards & Barron's default). Only curve it if the user clearly perceives diminishing
returns (e.g., the jump from $0 to $20k matters far more than $80k to $100k) — then anchor a few
points and interpolate. Don't over-engineer; linear is robust.

For purely qualitative units (e.g. "happiness", "stress"), score directly on 0-100 from the
research and the option descriptions — assign the best option ~100, worst ~0, others in between.
Say briefly why each score is where it is so it's auditable, not magic.

## Final aggregation

```
V(option) = sum_k  w_k * v_k(option)
```

Highest V = recommended pick. Sorting by V gives the full ranking. This is the simple additive
value model (SMARTER / MAVT) — valid under preferential independence (methods.md). It is
**compensatory**: a big win on one unit can offset a loss on another. That's usually what people
want, but flag it if a unit is genuinely non-negotiable (a hard constraint, not a tradeoff).

## Alternatives (only if asked / the decision warrants it)

If the user believes their priorities are nearly *flat* (units almost equally important), ROC's
steep profile overstates the top unit. Then rank-sum (RS) is gentler:

```
w_r(RS) = (N - r + 1) / [ N(N+1)/2 ]      # linear decline, flattest
```

Equal weights `w = 1/N` are the no-information baseline. Default stays ROC — it has the best track
record — but `vev.py` can emit RS / equal for a sensitivity comparison.
