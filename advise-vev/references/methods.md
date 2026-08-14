# Methods — the five papers, distilled

The academic grounding for `advise-vev`. You don't need this for a routine decision (SKILL.md +
roc-weights.md cover that). Read the relevant section when: a decision is high-stakes enough to
warrant heavier rigor, the user asks *why* the method is built this way, or you need to justify a
choice. Each method gets: the idea, the formula, and when (not) to use it here.

## Table of contents
1. SMARTER (Edwards & Barron 1994) — the spine
2. MAUT / MAVT (Keeney & Raiffa 1976) — the foundation
3. AHP (Saaty 1980) — pairwise weights, and why we avoid them
4. TOPSIS (Hwang & Yoon 1981) — distance-to-ideal
5. MCDA integrated view (Belton & Stewart 2002) — the philosophy
6. Which method when

---

## 1. SMARTER — Edwards & Barron (1994). THE SPINE.

"Simple Multi-Attribute Rating Technique Exploiting Ranks." The whole skill is a SMARTER
implementation that keeps the value vector visible.

Procedure: identify options -> identify value-units -> build the consequence table (raw outcomes)
-> drop dominated options -> linear 0-100 value functions per unit -> **rank the unit swings by
importance** -> ROC-convert ranks to weights -> additive aggregate -> sensitivity check.

The key move: SMARTER asks only for a **ranking** of the units, never numeric weights. It feeds the
ranking through the Rank-Order Centroid formula (roc-weights.md). Edwards & Barron's claim:
this performs ~98% as well as the heavier SMARTS that demands numeric swing weights, because precise
weights are false precision people can't reliably give anyway.

Why it's the spine: it's the most implementable of the five, asks the least of the user (fits "never
burden them"), and its rank-only elicitation is exactly what lets the skill avoid interrogating
people about their values.

---

## 2. MAUT / MAVT — Keeney & Raiffa (1976). THE FOUNDATION.

Multi-Attribute Utility/Value Theory. Establishes the additive model everything else builds on.

Additive **value** function (under certainty — what this skill uses):
```
V(x) = sum_i  w_i * v_i(x_i),    v_i in [0,1],   w_i >= 0,   sum_i w_i = 1
```

Two things to get right:

**Value vs utility.** A *value* function ranks sure outcomes. A *utility* function ranks lotteries
and additionally encodes risk attitude (concave = risk-averse). `advise-vev` operates under
certainty, so it builds a **value** model — call it that, don't mislabel it "utility." Only if a
decision is dominated by genuine risk/uncertainty would you reach for utility functions.

**Validity: preferential independence.** The additive form is valid when units are mutually
preferentially independent — your tradeoff between two units doesn't depend on the level of a third.
Usually close enough. If it clearly fails (units strongly interact — e.g. "good food" and "good
weather" multiply rather than add for a vacation), the additive sum distorts, and you'd need a
multiplicative form:
```
1 + K*U(x) = product_i [ 1 + K*k_i*u_i(x_i) ]
```
Rare in practice; note it and proceed additively unless the interaction is obvious and large.

**Weights are swing weights.** A weight is the value of swinging that unit from its worst to its
best level *across the range actually in play* — NOT abstract importance. This is the single most
important conceptual point and the reason scoring uses local ranges (roc-weights.md, vector-ev.md).

---

## 3. AHP — Saaty (1980). PAIRWISE WEIGHTS — AND WHY WE AVOID THEM.

Analytic Hierarchy Process. Structures the decision as goal -> criteria -> alternatives, and derives
weights from **pairwise comparisons** on a 1-9 scale (1 = equal, 3 = moderate, 5 = strong, 7 = very
strong, 9 = extreme). Weights = principal eigenvector of the comparison matrix. Consistency checked
via CR = CI/RI with CI = (lambda_max - n)/(n-1); accept if CR < 0.10. (RI table for n=1..10:
0, 0, 0.58, 0.90, 1.12, 1.24, 1.32, 1.41, 1.45, 1.49.)

**Why `advise-vev` does NOT use AHP by default — stated honestly:**
- **Burden.** n units need n(n-1)/2 pairwise comparisons (5 units = 10 questions, 8 = 28). That
  pesters the user — against the skill's core value. SMARTER needs one ranking (O(n)).
- **Rank reversal.** Adding/removing an option can flip the ranking of the others (Belton & Gear
  1983; Dyer 1990), because AHP normalizes relative to the option set.
- **The 1-9 scale is contested.** It's bounded and the verbal->number mapping lacks firm theory.

When AHP *is* worth it: a high-stakes decision with a few criteria where the user wants maximum
rigor on the weights and will tolerate the questions, and where catching weight inconsistency
matters. Then you can run pairwise comparisons and report CR. Offer it; don't impose it.

---

## 4. TOPSIS — Hwang & Yoon (1981). DISTANCE TO IDEAL.

Technique for Order Preference by Similarity to Ideal Solution. Intuition: the best option is
closest to a hypothetical best-on-every-unit point and farthest from the worst-on-every-unit point.

```
Normalize:  r_ij = x_ij / sqrt(sum_i x_ij^2)
Weight:     v_ij = w_j * r_ij
Ideals:     A+ = best per unit, A- = worst per unit  (flip for cost units)
Distances:  S_i+ = sqrt(sum_j (v_ij - v_j+)^2),  S_i- = sqrt(sum_j (v_ij - v_j-)^2)
Closeness:  C_i = S_i- / (S_i+ + S_i-)     # rank by C_i descending, near 1 = best
```

When TOPSIS helps here: many options (say 5+) scored on the same units, where "closest to ideal,
farthest from anti-ideal" is a natural lens and you want a cardinal 0-1 closeness score. It still
needs weights from somewhere — feed it the ROC weights. Caveat: TOPSIS also suffers rank reversal
when the option set changes, so pair it with the sensitivity check. For the common 2-4 option
personal decision, the SMARTER additive model is simpler and just as good; reach for TOPSIS when the
option set is larger.

---

## 5. MCDA integrated view — Belton & Stewart (2002). THE PHILOSOPHY.

The best modern survey, and the source of the skill's *attitude*. Three takeaways:

**MCDA supports decisions; it does not compute "the right answer."** The process is structure ->
model -> use-the-model-to-think, looping. The deliverable is a robust, understood recommendation and
the insight gained — not a precise score. (Phillips' "requisite model": you're done when probing the
model stops surprising you.)

**Three method families.** Value measurement (MAUT/MAVT/SMART — what this skill uses); goal/reference
(goal programming — for designing over large solution spaces); outranking (ELECTRE/PROMETHEE —
non-compensatory, can declare options incomparable, good when some criteria are non-negotiable).

**False precision is the enemy; sensitivity analysis is the cure.** Never trust one aggregate score.
Vary the weights/scores and see if the *recommendation* holds. If small defensible changes flip it,
the result is fragile and the user should know. This is baked into `vev.py` and the output contract.

---

## 6. Which method when (quick guide)

- **Default — any everyday decision, 2-5 options:** SMARTER additive + ROC. (SKILL.md flow.)
- **User wants maximum weight rigor, few criteria, tolerates questions:** add AHP pairwise, report CR.
- **Many options (5+) on shared units, want closeness-to-ideal:** TOPSIS, fed ROC weights.
- **A unit is genuinely non-negotiable (hard constraint):** don't let compensation rescue violators
  — filter them out first, then run SMARTER on the rest. (Outranking logic, lightweight.)
- **Decision dominated by risk/uncertainty:** move from value to utility functions; model the
  uncertainty explicitly. (Beyond the default; flag to the user.)

In all cases: keep the vector visible, end with one pick in plain language, run the sensitivity
check, and never judge the user's values.
