---
layout: post
title: "What a drug-target evidence agent gets wrong when the literature already knows the answer"
date: 2026-08-17 09:00:00
description: The card was pharmacologically correct and the conclusion was not in the retrieved evidence. That combination is the hard case.
tags: LLM evaluation reliability agents genetics drug-discovery
categories: engineering
giscus_comments: false
related_posts: false
toc:
  sidebar: left
---

I spent this summer building an agent that reads eight public biomedical databases through nine tools and
writes a one-page evidence card on whether a protein is worth pursuing as a drug target
for a given disease. The databases are UniProt, Open Targets (queried twice — once for target–disease
association, once for the clinical record), ChEMBL, ClinVar, gnomAD, the GWAS Catalog,
ClinPGx, and EpiGraphDB's pQTL resource, which holds *published* Mendelian
randomization estimates. MR, roughly, is the causal-inference method that uses genetic
variants as natural experiments to ask whether a molecule actually *causes* a disease
rather than merely tracking it.

The interesting failure was not a hallucination. It was this:

**The card wrote a conclusion that is pharmacologically correct, and that nothing it
retrieved supports.**

That combination is much harder to catch than a made-up number, because every check you
would normally run comes back clean, and every expert who reads it nods.

## The design: the model writes as little as possible

Tool outputs are captured verbatim. The evidence table, the caveats, the sources and the
provenance footer are rendered mechanically from them. The model writes exactly two
things — a one-line verdict and a short reasoning paragraph — and a validator (62
regression tests) rejects the run if that prose contains a number, an rsID or an
identifier that appears nowhere in the tool output.

Then I attacked it with 41 adversarial agents across four critic lenses, with every
allegation re-checked by an independent skeptic before it counted: 86 alleged, 27 upheld,
**18 confirmed distinct defects**. My validator's recall against those 18 was **zero**.

Every check I had written was necessary. None of them covered the failures that mattered.

## The case

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

The card quoted that correctly, and concluded:

> **GO** — genetic and Mendelian randomization evidence supports a causal, **protective
> role of IL6R inhibition** in coronary heart disease.

My first reading was that this was backwards. The exposure in that resource is *plasma
IL6R protein level*. A negative beta says genetically **higher** IL6R protein goes with
**less** coronary heart disease — so, I reasoned, the data licenses a claim about raising
the target, and the card recommended inhibiting it.

That reading was wrong, and the way it was wrong is the point of this post.

## Why the card was right

IL6R's instrument, rs4129267, is a near-perfect proxy (r² ≈ 0.96–0.99 in Europeans) for
rs2228145, the Asp358Ala missense variant. The 358Ala allele accelerates ADAM-mediated
shedding of the receptor's ectodomain. That **raises soluble IL6R in plasma while
impairing classical IL-6 signalling**, and it lowers C-reactive protein and coronary
heart disease risk. It is the variant that genetically mimics tocilizumab.

So "genetically higher plasma IL6R" and "IL-6R blockade is protective" are not opposites.
They are the same statement, once you know that the measured plasma species is a shed
decoy rather than the signalling receptor.

The card had it right. And **not one field it retrieved contained that mechanism.** The
model supplied it from memory, and happened to be correct.

That is the failure mode I now worry about most. Not a hallucinated fact — a *correct
conclusion that the retrieval does not support*. A domain expert skimming the card nods,
because the sentence is true. The reviewer fills the gap from their own memory, exactly as
the model did, and the pipeline's silence is laundered through the reader's expertise.

Next time the remembered answer will be stale, or wrong, or right for a different protein.
Nothing in the system can tell the difference.

## The part that is measurable

Two cards in the same batch, same outcome, same tool:

```text
IL6R   beta -0.0442  p 2.21e-07  n_snp 1  steiger NA    ld_check null  coloc null
LPA    beta +0.2523  p 5.39e-39  n_snp 1  steiger TRUE  ld_check 1.0   coloc null
```

LPA's estimate passed a Steiger direction test and an LD check. IL6R's passed neither, and
has no colocalization either. A one-SNP Wald ratio with none of those three cannot
distinguish a causal effect from linkage disequilibrium with a neighbouring gene, or from
reverse causation.

**Both cards used the same strength of language.** "Supports a causal role", in both.

That is a defect you can encode, so I did. The validator now fails any run that uses causal
wording on a single-instrument estimate whose Steiger, colocalization and LD check are all
absent. When I re-ran the benchmark, it fired on exactly the card it was built for — and
note the direction of travel, the model was *more* confident this time, not less:

| | verdict | result |
|---|---|---|
| before | "genetic and **causal** evidence support IL6R as a promising target" | passed |
| after | "…indicate a **causal** and safe target for coronary heart disease" | **failed** |

## The deeper question: what does a plasma pQTL actually instrument?

Once you take the IL6R case seriously, a more uncomfortable question follows. A plasma
protein concentration is not one quantity. It is the net of

```text
synthesis -> secretion -> proteolytic processing / ectodomain shedding
          -> complex formation -> receptor-mediated and renal clearance
          -> and finally, whether the assay reagent still binds
```

Only the synthesis route makes "higher plasma level" mean "more pathway activity". Every
other route can decouple the two, and the last one can decouple the measurement from
reality altogether: affinity proteomics measures *binding*. A missense variant in the
assayed protein can change how well the reagent binds without changing how much protein is
there. Published cross-platform comparisons find that of the proteins with cis-pQTLs
detected on both SomaScan and Olink, about a third carry a missense variant, and dozens
show **opposite effect directions between platforms for the same variant**.

IL6R's instrument tags a missense variant in IL6R itself. So the honest position is that
the estimate could have been an assay artefact — it happens not to be, because there is
independent wet-lab evidence for the shedding mechanism, but nothing in the retrieved
fields lets you tell those apart.

I wanted to know how often this could bite, so I asked which studies the resource actually
draws on. That field was there all along, in a view the tool was not reading. Censused
across all 991 proteins:

| study | rows | n | platform |
|---|---|---|---|
| Sun | 60,754 | 3,301 | SomaScan |
| Emilsson | 22,370 | 3,200 | SomaScan |
| Suhre | 10,836 | 984–997 | SomaScan |
| Yao | 6,031 | 6,861 | SomaScan |
| Folkersen | 1,834 | 3,394 | Olink |

Four aptamer studies, one antibody study, and **no mass spectrometry at all**. MS is the
one platform that counts peptides instead of binding them, which makes it the natural
referee for the epitope question — and it is not in there. The question cannot be
adjudicated anywhere inside the resource.

There is a smaller consequence too, which I had been committing without noticing: IL6R
comes from Folkersen (Olink, n=3,394) and LPA from Yao (SomaScan, n=6,861). Putting their
estimates side by side on one card is a cross-platform, cross-cohort comparison. Nothing
in the output said so.

## The fix: classify the mechanism instead of refusing to answer

My first instinct was to make the tool refuse: *the retrieval does not cover drug action,
so do not claim it.* That is a safeguard that explains nothing, and it is not what anyone
would pay a target-validation group for. The useful question is **when** the sign inverts,
and whether you can call it in advance.

You can, because those routes leave different retrievable fingerprints. UniProt annotates
topology and proteolytic processing; Ensembl VEP annotates what the instrument does. Put
them together and the class falls out:

| protein | evidence retrieved | class | sign |
|---|---|---|---|
| IL6R | transmembrane, a separately annotated soluble species, PTM comment "a short soluble form is released from the membrane"; instrument tags a missense at position 358 | `shedding_decoy` + `assay_epitope_risk` | **inversion expected** |
| LPA | no transmembrane segment, no shedding annotation, intronic instrument | `production` | preserved |
| PCSK9 | annotated autolytic and furin cleavage | `processing_cleavage` | direction preserved, **magnitude not interpretable** |

PCSK9 is worth a sentence on its own. Because the assay pools active and inactive species,
a one-SD change in what was measured is not a one-SD change in the active pool. The
direction survives; the effect size should be read as ordinal, not as a dose.

## Checking the classification against data

A classification that only sounds right is not worth much, so the next question is whether
it predicts anything. It does, and the check costs nothing: the GWAS Catalog serves every
association for a variant, free and unauthenticated. The only subtlety is that each study
reports its beta against whichever allele it called the risk allele, so comparing them
unflipped is precisely how sign errors get made. Anchor everything to one allele and read
the protein against its downstream markers.

**IL6R**, anchored on the C allele: the protein measurement moves −1.21, −1.14, −1.11
across six separate studies. Of seven other traits with a signed effect, **four move the
opposite way** — including C-reactive protein, the canonical downstream readout of IL-6
signalling. The allele that lowers soluble receptor raises CRP.

**PCSK9**, anchored on the A allele: the protein moves −1.07. Of nine other traits, **eight
move the same way** — LDL cholesterol at −0.50, −0.39, −0.39, total cholesterol at −0.47.

The mechanism class predicted inversion for one and preservation for the other, and
independent summary data agreed with both. No bulk download, no controlled-access
application, no individual-level data.

One more thing fell out of that pass. PCSK9's instrument, rs191448950, is labelled *cis* in
the resource — but VEP annotates its transcript consequence to **USP24**, the neighbouring
gene. "cis" is a position window, not evidence that the variant acts on the gene you think
it does. That is exactly the confounding a single-instrument estimate with no
colocalization cannot exclude, and it is now flagged on the card.

## The second lesson: pass rate is a vanity metric

Ten of ten cards passed validation. I nearly wrote that number down as progress.

Then I counted what was left to check: **three checkable tokens in the whole batch.** The
model had learned that the safe move is to stop making claims that can be checked. It
passed everything by asserting almost nothing.

Later I made the validator stricter, and the same benchmark dropped to 8/10 — both failures
were the model asserting clinical status ("clinically proven", "approved") that none of the
retrieved sources returns. **A pass rate that falls when the check gets honest is what progress
actually looks like.**

So the pipeline now reports **claim density** — checkable tokens per 100 words of reasoning
— beside the pass rate. Neither means much alone. Together they say something real: how
much did it claim, and how much of that held up? The run as this was written: 8/10 passed, 2
checkable tokens across 842 words, 0.20 per 100 words. That is worse than the run before
it, and reporting it is the point.

I also had to be careful about the rule itself. An early version of the direction check
rejected a sentence that was correct. A check that punishes you for being precise just
teaches you to be vague, which is the opposite of what any of this is for.

## What I'd take from this

1. **"The model was right" is not the same as "the pipeline supported it."** Track the
   second one. The first will keep being true until it suddenly isn't, and you will have
   built no way to notice.
2. **An estimate existing is not an estimate being validated.** If your sources carry
   sanity checks, make the language your system is allowed to use depend on them.
3. **Ask what your measurement is actually measuring.** For plasma proteins the answer is
   often "reagent binding, filtered through shedding and clearance" — and the class is
   derivable from annotations you already have.
4. **Report how much was checkable, not just how much passed.** A pass rate without claim
   density measures caution, not accuracy.
5. **Adversarially test guardrails before trusting them.** I would have shipped mine with a
   clean conscience. Recall 0/18 is not a number you discover by staring at your own code.

## Postscript, four days later: the same failure, caught

*Added 2026-08-21.*

The failure this post is about — the model supplying from memory what retrieval did not
give it — is one I could not catch when I wrote this. So I built a check for it and then
went looking for it somewhere I had not chosen the data.

I scored the agent against twenty target–indication pairs sampled from [Minikel et al.,
*Nature* 2024](https://doi.org/10.1038/s41586-024-07316-0): ten drugs that launched, ten
programmes that died at phase II/III. History supplies the labels, not me. I withheld the
clinical-evidence tool, because it reports approval stages directly and would hand the
agent the answer.

**On two of the twenty cards the validator caught the model importing knowledge it had not
retrieved, and failed the run.** One card asserted that a target had "multiple approved
inhibitors" — true, and nowhere in what the pipeline had fetched. That is the IL6R
failure again, and this time the system noticed instead of me.

The verdicts themselves held up better than I expected: every GO the agent issued was a
drug that launched, and it endorsed none of the ten failures. I am not claiming that as a
result — n is twenty, and an audit of the run showed part of that precision rides on
residual clinical signal inside an association score rather than on genetics alone. I am
claiming something smaller and, to me, more useful: **the errors were all abstentions.**
When the retrieval was thin, the agent declined rather than reached.

The code, the 62 regression tests and the audit are open, in the repo built during the CABS
2026 data science internship. The MR estimates throughout are *retrieved*: the exposure side
comes from EpiGraphDB's pQTL resource (Zheng et al., *Nature Genetics* 2020, aggregating the
five studies above) and the outcome side from separate published GWAS. This agent computes
no causal inference of its own, which is exactly why getting the interpretation right
matters so much.

*Thanks to the CABS 2026 cohort for the arguments that shaped this — including the one that
made me go back and check whether the sign was really inverted at all.*
