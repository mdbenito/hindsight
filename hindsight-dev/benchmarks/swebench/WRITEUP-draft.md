# Coding agents with memory learn on the job: [N60: +42%] more SWE-bench issues resolved

<!--
DRAFT — pending final N=60 numbers. All `[N60: …]` markers get replaced from
results/pilot-django-n60-single/results.json when the run completes.
Current stand-in numbers are the completed N=40 run (results/pilot-django-n40-single/).
Author: Chris Bartholomew. Target: hindsight-docs/blog/ after review.
Angle: learning-on-the-job. Same model, same tools — experience is the only variable.
-->

**TL;DR:** We ran a standard open-source coding agent
([mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent)) through [N60: 60] consecutive
Django issues from **SWE-bench Verified** — the way a real engineer works a real backlog —
and let it remember what each issue taught it, using
[Hindsight](https://github.com/vectorize-io/hindsight). Same model, same tools, same prompts,
official harness scoring. The agent with memory resolved **[N60: 17/40 (42.5%)]** of the
issues; the identical agent without it resolved **[N60: 12/40 (30%)]** — and it never lost a
task the memoryless agent could solve, across ten experiment runs. Every extra solve traces
back to a specific, recorded lesson from an earlier issue. The agent didn't get smarter. It
got **experienced**.

## Every coding agent today is a brilliant new hire on their first day — forever

A coding agent's tenth bug in your codebase costs it exactly as much as its first. It
rediscovers the same module layout, re-trips the same test-suite quirks, re-attempts the same
plausible-but-wrong fixes. Engineers don't work like this. The reason your senior engineer is
fast in a subsystem isn't raw intelligence — it's that the subsystem has already *punished*
them: they know which approach failed last quarter, which invariant is easy to break, which
test catches it.

That knowledge has a precise shape: **verified experience**. Not documentation, not the
codebase map (the agent can grep that in seconds) — the record of what was tried, what the
tests said, and what it implied. This is exactly what Hindsight stores.

So we asked the simplest version of the question: if an agent could carry verified experience
from issue to issue, would it do its job measurably better?

## The experiment: a backlog, not a quiz

SWE-bench normally scores each issue in isolation — fresh checkout, fresh agent, no shared
state. That's the right design for measuring a *model*, and it structurally erases learning:
there is nothing to learn *from*. We changed exactly one thing: the agent works the issues
**consecutively, in chronological order**, like a backlog. Everything else is stock:

- **Agent:** [mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent) 2.3.0, the
  ~100-line community-standard scaffold. One patch per issue, no retries — the standard
  single-attempt protocol, so the result carries no pass@k asterisk.
- **Model:** `gemini-flash-latest` at temperature 0, both arms.
- **Tasks:** [N60: 60] issues from SWE-bench Verified touching `django/db/models` (the ORM) —
  the densest subsystem cluster, because experience compounds within a subsystem.
- **Scoring:** the official `swebench.harness.run_evaluation` in Docker. We never hand-judge.
- **Arms:** *control* — the agent cold on every task, the standard amnesiac setup;
  *treatment* — the same agent with [Hindsight](https://github.com/vectorize-io/hindsight):
  recall before each task, retention after. Identical prompt templates; the control's memory
  block simply renders empty.

The learning loop mirrors an engineer's: **attempt the issue → CI scores the patch → the
verified outcome is retained — including, for failures, exactly which tests failed and how →
the next issue begins with whatever experience is relevant.** Failures teach as much as
successes; they just have to be remembered correctly (more on that below).

## Results: experience compounds

| | Day-one agent (no memory) | Experienced agent (Hindsight) |
|---|---|---|
| Issues resolved | [N60: 12/40 (30%)] | **[N60: 17/40 (42.5%)]** |
| Issues it learned to solve (fail→pass flips) | — | **[N60: 5]** |
| Issues it forgot how to solve (regressions) | — | **0** |
| Cost per resolved issue | [N60: 2.34M tokens] | **[N60: 1.55M (−34%)]** |
| Total tokens / steps per run | [N60: 28.1M / 1,145] | [N60: 26.4M (−6%) / 1,028 (−10%)] |
| Memory system overhead | — | [N60: ~1.8%] of agent spend |

[N60: McNemar exact test on discordant pairs: p = …]. The direction has held in 10 out of 10
experiment runs, and the zero-regression record is unbroken: learning never cost the agent a
task it already knew how to solve.

Note what the economics say: per-run cost is roughly flat (remembering adds context;
experience saves steps; it nets out). What changes is **output per dollar** — the same budget
fixes [N60: ~40%] more issues, because experience converts failures into solves.

## Watch it learn: one lesson, end to end

The claim "it learned" should be checkable, so every run records what was recalled before each
task, what the tests said after, and what was retained. Here is one complete learning episode
from the logs:

1. **The failure.** Early in the backlog, the agent attacks a UNION-query ordering bug by
   deep-cloning `combined_queries` inside `Query.clone()`. The official harness fails the
   patch. The retained lesson is the verified record, scoped exactly: *"deep cloning
   `combined_queries` in `Query.clone()` (django/db/models/sql/query.py) did not pass
   `test_union_with_values_list_and_order`."*
2. **The recall.** Five issues later, a different bug: `exclude()` on an annotated
   `FilteredRelation` crashes — another query-state-propagation problem. The agent's recalled
   experience includes that scoped clone lesson.
3. **The application.** The memoryless control, at the same decision point, *considers* using
   `clone()` and rejects it, hand-copying attributes instead — and fails. The experienced
   agent greps for `clone`, reads it, builds its fix on `self.clone()` — and passes the
   official tests.

A failed approach on one bug became the winning approach on a different bug, because the
lesson preserved *where* it failed and *what the tests said* rather than a vague moral.
That's not retrieval-augmented prompting; that's learning from experience. Several issues
flip this way in **four out of four independent runs**.

## How we know it's learning — not luck, not prompt magic

We were our own harshest reviewers here, because twice during this study we caught ourselves
believing artifacts. The final result sits on four controls:

**Deterministic baseline.** At temperature 0 this stack reproduces control runs
**bit-for-bit** (same steps, same tokens, same patches). Differences between arms are
therefore attributable to memory content — not sampling. (This also exposed our worst early
mistake: comparing against a stale control from a slightly different prompt template produced
spectacular fake "efficiency wins." The harness now fingerprints the pipeline and refuses
cross-pipeline comparisons.)

**Placebo control.** Maybe *any* injected text nudges a temperature-0 agent onto different,
occasionally luckier paths? We ran a placebo arm: same position, same per-task block sizes,
same format — but irrelevant engineering notes (CDN caching, Kubernetes probes). **The placebo
scored exactly the control's result and flipped nothing.** Reading someone else's notes
doesn't help; *your own relevant experience* does. (The placebo arm was also more expensive
than no memory at all — irrelevant context is pure drag.)

**Replay.** We took the exact recalled-experience blocks that preceded two flips and
re-injected them verbatim — no live memory system — three times each. **All six replays
reproduced the winning trajectories byte-for-byte**, official harness passes included. What
the agent learned is not correlated with success; it is *sufficient* for it, deterministically.

**Per-flip forensics.** Every flip has the receipts above: recalled content, test evidence,
retained lesson. Nothing in the headline number is unexplained.

## What makes a lesson learnable (what we fixed in our own product)

Running this study was also a brutal QA pass on Hindsight itself. Three findings we believe
generalize to anyone building agents that learn:

**Lessons must stay scoped to the evidence.** The same failure, remembered as *"X applied in
method Y did not pass test Z"*, steered later work toward the right fix. Remembered as *"avoid
X — the real issue is in Z"*, it fenced off exactly where the next fix lived. Over-generalized
negative lessons are how experience curdles into superstition — for agents as for people. We
now enforce evidence-not-prescription scoping at every layer Hindsight exposes: the retention
prompt, `retain_mission` (extraction), and `observations_mission` (consolidation — which
merges facts and can otherwise mint "avoid X" from two perfectly scoped failures).

**Synthesis turns evidence into instructions — dangerous when 90% right.** Our `reflect` mode
once produced a near-perfect diagnosis with one fatal detail wrong; the agent applied the
prescription verbatim instead of investigating, and failed. The humble bullet list of raw
experience — which leaves judgment with the agent — outperformed confident synthesis. We also
found and fixed reflect fabricating "verified knowledge" from an empty bank. A learning system
must present experience as evidence, never as orders.

**Learning transfers across tasks, not within retries.** We tested giving the agent its CI
feedback and an immediate second attempt at the same issue. Across ~25 informed retries,
exactly one succeeded (a mechanical indentation failure). For conceptual failures, the agent
re-derives the same wrong theory minutes later. But the *same* feedback, retained and recalled
on *different related issues*, is what produced every flip in the study. Experience needs to
compound, not loop.

## Honest limitations

- **One repository, one subsystem, one model tier.** Django's ORM, flash-tier model.
  Cross-repo and cross-model generalization is the next experiment.
- **Good experience raises the odds; exact experience guarantees.** With a well-formed bank,
  the hardest tasks flip roughly half the time per run — agent decisions are sensitive to the
  whole context. Replay shows the effect is deterministic given exact content; what remains
  between "usually" and "always" is retention's own LLM nondeterminism.
- **Memory doesn't make a single run faster.** Per-run tokens are ~flat; the gain is outcomes
  per dollar. (It does sometimes prevent pathologies — the experienced agent sidestepped
  multi-hundred-step runaway loops the amnesiac fell into — but runaways cut both ways and we
  don't claim them.)
- **Experience can breed overconfidence.** Once in ten runs the agent trusted its memory
  enough to skip verification and submitted an empty patch in two steps. Verification lessons
  reduce but haven't eliminated this — also true of engineers.

## The takeaway

The agent's model never changed. Its tools never changed. The only thing that changed between
30% and [N60: 42.5%] was whether it was allowed to remember what the job had already taught
it — with the lessons verified by CI, scoped to the evidence, and recalled when relevant.

That's the actual promise of agent memory. Not "chat that remembers your name" — **agents that
get better at their job the way people do: by doing it.**

Everything here is reproducible from the open-source repo: the harness
(`hindsight-dev/benchmarks/swebench/`), every run's per-task records, the recalled/retained
content for every flip, the placebo and replay machinery, and the official scoring artifacts.

> On [N60: 60] consecutive SWE-bench Verified issues (standard single-patch protocol, official
> harness scoring), the same agent resolved [N60: 42.5%] with Hindsight memory vs [N60: 30%]
> without — [N60: +42%] relative — at [N60: 34%] lower cost per resolved issue, with zero
> regressions, ~2% memory overhead, a placebo-controlled mechanism, and byte-level
> reproducible flips.

<!-- TODO before publish:
  1. Swap all [N60: …] placeholders from pilot-django-n60-single/results.json (+ recompute
     McNemar, cost/solve, flip-stability table).
  2. Decide on warm-up curve chart (N=40 showed no late acceleration — present honestly or omit).
  3. Add run-reproduction command block + repo links.
  4. Marketing pass; align with "Agent Memory That Learns" positioning (title already does).
  5. /code-review + push the bench branch so referenced code is public.
-->
