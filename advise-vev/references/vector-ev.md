# Vector EV — the idea, and the guardrails

Read this to understand *why* `advise-vev` keeps value as a vector, and the honesty rules that keep
it from manufacturing false confidence. The math lives in roc-weights.md; this is the philosophy
that decides how you present it.

## What "Vector EV" means

Most decisions involve several kinds of value that don't share a currency: money (dollars),
happiness (satisfaction), time (hours), health (life-quality), risk, status. The classic methods
(MAUT, TOPSIS, SMARTER) all eventually crush these into **one number** to produce a ranking.
"Vector EV" is the discipline of **not crushing prematurely**: keep value as a vector with one
component per unit, show the user that vector, and only collapse to a single scalar at the very
end — with the weights visible.

The expected-value framing: each option has a value *vector* across units. To pick, you eventually
project it onto a single axis using weights (how much each unit matters). The projection is the
scalar EV. But the vector is where the truth lives — it shows *what you trade for what*. The scalar
just says who won.

## Vector-first, scalar-last (the output contract)

Always lead with the per-unit tradeoff, end with the single pick:

1. **The vector table** — each option scored 0-100 on each unit. This is the star. The user should
   see "Option A buys money at the cost of time" directly.
2. **The weights** — shown, with one line on where they came from (the ranking the user gave or
   confirmed -> ROC).
3. **The scalar ranking + the pick** — last, in plain language (Auto-Clarity).
4. **The sensitivity note** — does the pick survive small changes to the ranking?

Why this order: Belton & Stewart (2002) warn that leading with a single number manufactures false
confidence. A clean "73.4 vs 71.9" *looks* like a measurement but is a summary of soft judgments.
Showing the vector first keeps the user oriented to the real tradeoff, so the scalar is read as
"here's how it nets out," not "here's the truth."

## The false-precision guardrails (non-negotiable honesty)

These are what separate an honest decision aid from a magic-number generator.

- **Never present the scalar as exact truth.** It's a summary of judgments. A 2-point gap is not a
  real difference. Say "close" when it's close.
- **Always run the sensitivity check.** `vev.py` tests whether the winner survives adjacent rank
  swaps. If a single defensible swap flips the result, the pick is *fragile* — say so plainly.
  Phillips' "requisite model": you trust the model once probing it stops producing surprises. A
  fragile result means the decision genuinely hinges on a value judgment the user should look at.
- **Weights are tradeoffs over the actual ranges, not abstract importance.** "Money matters more
  than safety" is meaningless until you know how much they vary across the options. If every option
  is equally safe, the safety swing is tiny and deserves little weight no matter how "important"
  safety is in the abstract. This is the swing-weight insight (methods.md) — honor it when scoring.
- **Compensation is a choice, not a law.** The additive model lets a big win on one unit offset a
  loss on another. Usually fine. But if a unit is a hard constraint ("must be under $X", "cannot
  involve relocating"), that's not a tradeoff — flag it and treat options that violate it as out,
  rather than letting a high score elsewhere rescue them.
- **Show where the winner wins and loses.** Never just "A wins." Say "A wins on money, loses on
  time." That single sentence is often more useful to the user than the number.

## What the user should walk away with

Not a number. A **robust, understood recommendation**: the pick, what it costs them in the units
they care about, and how confident they can be given how the result moves if their priorities
shift. That's decision *support* — the thing the whole MCDA literature says the output should be.

## Tone reminder

Caveman voice (full) for the vector and reasoning; plain sentences for the pick and any caveat.
Never judge the user's options, values, or ranking. If their priorities surprise you, that's not
your business to question — score honestly against the priorities they gave and help them see the
consequence. You are there to help them decide, not to grade their values.
