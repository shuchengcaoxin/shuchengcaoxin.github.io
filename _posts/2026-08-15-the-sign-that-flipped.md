---
layout: post
title: "My agent quoted β = −0.044 correctly, then recommended the opposite drug"
date: 2026-08-15 10:00:00
description: What 41 adversarial agents found in an LLM evidence pipeline — and why the fix wasn't a better prompt
tags: LLM evaluation reliability agents genetics
categories: engineering
giscus_comments: false
related_posts: false
toc:
  sidebar: left
---

I spent this summer building an LLM agent that reads eight public biomedical databases and
writes a one-page evidence card about whether a protein is worth pursuing as a drug target
for a disease. Every claim on the card carries a source link and a database release
version. I was fairly proud of the guardrails.

Then I attacked it with 41 agents, and my guardrails caught **none** of the 18 real defects
they found.

This post is about the worst one, because I think it generalises well beyond genetics: the
card cited the right number and drew the opposite conclusion, and no amount of prompting
would have prevented it.

## The setup

The agent takes a protein and a disease. It calls eight databases — protein annotation,
target–disease association, known drugs, clinical variants, population constraint, GWAS
associations, pharmacogenomics, and a Mendelian randomization (MR) resource that holds
*published* causal estimates. MR, very roughly, is the causal-inference method that uses
genetic variants as natural experiments to ask whether a molecule actually *causes* a
disease rather than merely tracking it.

The design principle was: **the model writes as little as possible.** Tool outputs are
captured verbatim, and the evidence table, caveats, sources and provenance are rendered
mechanically from them. The model writes exactly two things — a one-line verdict and a
short reasoning paragraph — and a validator (29 regression tests) rejects the run if that
prose contains a number, an rsID or an identifier that appears nowhere in the tool output.

That validator catches fabrication. It does not catch what happened next.

## The failure

For **IL6R × coronary heart disease**, the MR tool returned:

```text
beta   -0.0441899892357374
se      0.00853005023322569
p       2.21e-07
method  Wald ratio      n_snp 1
instrument rs4129267    cis
steiger_direction_ok  NA
coloc_prob            null
ld_check              null
```

The card quoted that estimate **correctly**. Then its verdict read:

> **GO** — genetic and Mendelian randomization evidence supports a causal, **protective
> role of IL6R inhibition** in coronary heart disease.

Look at the sign. In this resource the exposure is **plasma IL6R protein level**. A
negative beta says: genetically *higher* IL6R protein goes with *less* coronary heart
disease. Read from the retrieved data alone, that licenses a claim about *raising* the
target. The card recommended **inhibiting** it — the opposite intervention.

Every fact on the card was right. The conclusion contradicted the data it was standing on.

## The control is what makes this evidence rather than an anecdote

In the same batch, against the same outcome, through the same tool, the **LPA** card
received `beta = +0.252` and wrote that elevated LPA *increases* coronary heart disease
risk — the sign convention applied correctly.

Same code, same prompt, same run. The direction was silently flipped **only** for IL6R.

Why IL6R? Because IL6R × coronary heart disease is famous. There is a well-known
literature story in which a receptor variant mimics IL-6 blockade, and IL-6 blockade is
cardioprotective. The model had that conclusion memorised, and when the retrieved number
disagreed with the remembered answer, the remembered answer won.

That is the failure mode I now worry about most: **not hallucinated facts, but a correct
citation attached to a recalled conclusion.** A domain expert skimming that card would
nod — the sentence is *true in the literature*. But the mechanism that makes it true
appears in exactly zero fields of that run. The reviewer supplies it from their own
memory, exactly as the model did, and the pipeline's failure is laundered through the
reader's expertise.

## Why the validator was blind

My checks were token-level: does every number, rsID and accession in the model's prose
appear in the tool output? Here, they all did. There was nothing to flag. The validator
had no representation of *what the exposure was* or *what raising versus lowering it would
mean*, so this class of error was invisible by construction.

The adversarial audit made the scale of that blind spot measurable. Four critic lenses
attacked the ten benchmark cards; every allegation was re-checked by an independent
skeptic before it counted. 86 alleged → 27 upheld → **18 confirmed distinct defects**.
My validator's recall against those 18: **0**.

Every check I had written was necessary. None of them covered the failures that mattered.

## The fix: take the pen away

You cannot prompt your way out of a memorised answer. You can add "be careful about
effect direction" to the system prompt, and the model will agree with you and then do it
again, because the failure isn't inattention — it's a stronger prior overriding a weaker
input.

So the direction sentence is no longer the model's to write. The renderer now emits it
mechanically from `sign(beta)`:

> Genetically-predicted **higher plasma IL6R** is associated with **LOWER Coronary heart
> disease** (beta −0.04419, se 0.00853, p = 2.21e-07; Wald ratio, n_snp 1, instrument
> rs4129267, cis).
>
> - Not available for this estimate: Steiger direction, colocalization, LD check.
> - Single-instrument Wald ratio: no heterogeneity or pleiotropy test is possible.
>
> **The exposure is IL6R protein abundance, not a drug.** This run retrieved no evidence
> about what pharmacological inhibition or activation of IL6R does.

And the validator gained a direction lock: if the model's prose claims a therapeutic
direction that contradicts the sign of beta, the run fails. It deliberately ignores
"higher/lower/increase/decrease" — in these cards those describe the *outcome*, not an
intervention, and an earlier version of the rule rejected the correct sentence *"higher
IL6R protein is associated with lower disease risk."* A rule that punishes an accurate
description teaches the writer to be vaguer, which is the opposite of what you want.

The general principle: **for anything you can check mechanically, don't let the model write
it.** Not "instruct the model more firmly" — remove the opportunity.

## The second lesson: pass rate is a vanity metric

After I hardened the prompt, the batch went from 7/10 to **10/10 passing**. I nearly
wrote that number down as progress.

Then I counted what was left to check: across 915 words of model-written reasoning, the
validator found **3 checkable tokens**. The model had learned that the safe move was to
stop making claims that could be checked — all prose, no numbers. It passed everything by
asserting almost nothing.

A card that asserts nothing is not a safe card; it is an unfalsifiable one. So the
pipeline now reports **claim density** — checkable tokens per 100 words of reasoning —
next to the pass rate. Neither number means much alone. Together they say something real:
*how much did it claim, and how much of that held up?*

If you are evaluating an LLM system and reporting a pass rate without reporting how much
there was to pass on, you may be measuring the model's caution rather than its accuracy.

## What I'd take from this

1. **Sign, direction and polarity errors are a distinct failure class**, and token-level
   validators are structurally blind to them. If your domain has a direction — a treatment
   effect, a trade signal, a control action — encode it as a rule, not a request.
2. **Test the guardrails adversarially before you trust them.** I would have shipped mine
   with a clean conscience. Recall 0/18 is not a number you discover by staring at your
   own code.
3. **Look for the correct-citation-wrong-conclusion pattern.** It survives review precisely
   because the sentence is true; the expert reader fills the gap from memory and never
   notices the pipeline didn't.
4. **Report how much was checkable, not just how much passed.**

The code, the 29 regression tests and the audit are open, in the repo built during the
CABS 2026 data science internship. The MR estimates throughout are *retrieved* from
published work (Zheng et al., *Nature Genetics* 2020, via EpiGraphDB) — this agent
computes no causal inference of its own, which is exactly why getting the direction
sentence right matters so much.

*Thanks to the CABS cohort, and to Natalie Huang, whose drug-safety module is the
companion piece to this one.*
