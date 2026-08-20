# Pre-registration — Agreement-corroboration filter (the principled repair of §7.1)

*Locked before running. 2026-08-11. Mirrors `classifier_prereg_20260801.md` discipline.*
*Trigger: user's repeated, correct concern that the four survival tests must include a genuinely*
*cyst-tailored attempt, not only borrowed/coverage methods. This is that attempt.*

## 0. Framing (positions the test correctly, and answers the strawman concern)

This is **not** a new virgin method family. §7.1 already tested the cross-model **agreement**
family, using a **global-Dice** agreement metric, and it failed (deletes true cyst in 52–56% of
cyst-positive cases; every threshold below baseline HEC — `cross_scale_sweep.txt`). We diagnosed
**why** it failed: global Dice assumes the two models delineate the *same object*, which is false
for small, dispersed cysts, so a *correct* cyst gets a low cross-model Dice and is deleted.

The agreement-corroboration filter is the **dispersion-aware repair** of that diagnosis: instead of
whole-component Dice, keep a predicted-cyst component only if an independent raw model (lowres **or**
resenc — *not* fullres) predicts cyst **anywhere within a spatial tolerance τ** of it. This directly
attacks the mechanism that killed §7.1, and it targets the measured structural quirk: **39.7% of
residual-FP voxels are Fullres-only** (`typeX_full_breakdown.json`), and the pipeline's intersection
vote never required independent corroboration because Fullres is shared across both voting pairs
("named intersection, behaves as F single-model dictatorship" — CLAUDE.md §6).

Whether it works is an **empirical** question with a clean pre-condition (§2). It is training-free,
runs on existing hold-out predictions, pure CPU, does not touch the CV.

## 1. Method (fixed)

- Input: fold-0 hold-out. Per-case final prediction (`soft_majority_rule3_typex`), raw
  lowres/fullres/resenc predictions, GT.
- For each predicted-cyst connected component C, define **corroboration**: ∃ a voxel labelled cyst
  by lowres OR resenc within Euclidean distance τ of C.
- Rule: **keep** C if corroborated; else **remove** (relabel to kidney) — same destination as Type X.
- τ swept over a **pre-specified** set: **{0, 2, 4, 6, 10} mm** (physical units, spacing-aware
  distance; 0 = strict co-location = §7.1-like; larger = more dispersion-tolerant). No τ outside this
  set is reported post-hoc, and **all five are reported** (no cherry-picking).
- Corroboration counts **cyst** predictions only, not tumour/mass: the taxonomy artifact shows resenc
  predicts *mass* over **70.0%** of residual-FP voxels while predicting *cyst* over only 23.4% —
  mass-level corroboration would retain most false positives and is declared out of scope for that
  reason (the 70.0% figure is reported as the justification, not tested).

## 2. Descriptive pre-check (run and report BEFORE the operating-point analysis)

Measure the **TP-side** combo distribution — for **true** cysts (GT-cyst voxels the pipeline
correctly predicts), what fraction are Fullres-only vs L/R-corroborated at each τ. (We have only the
**FP-side** combo so far: F-only 39.7%, LF 35.9%, LFR 12%, FR 11.1%.)

- **Role (amended at sign-off): descriptive mechanism evidence only.** It explains *why* the filter
  succeeds or fails (if true cysts are as uncorroborated as FP, the coupling persists; if a gap opens,
  the filter has leverage) but it does **not** gate the analysis — a qualitative go/no-go here would be
  a wiggle point. The §3 criterion alone decides; both computations run in the same pass regardless.

## 3. Success criterion (fixed, mirrors the classifier pre-reg)

Success = a **safe operating point** exists: some **single τ** from the declared set at which, **case-level**,
- FP-alarm cases cleared **>** cyst-positive cases that lose **≥ 1 true-positive cyst component**
  (conservative cost count: any TP-component loss counts, not only full case-level FN flips; both
  counts are reported), **and**
- meaningful recovery: **≥ 25%** of the 16 residual FP cases cleared (≥ 4 cases), **and**
- mean HEC within **−0.001** of the corrected baseline (0.9020), **and**
- **replication gate (amended at sign-off):** the **same τ** satisfies all of the above on **folds 1
  and 2** (predictions already exist from the CV spot-checks). Five τ values against 16 cases is
  enough multiplicity that a fold-0-only "safe point" can be luck; a point that fails to replicate is
  reported as outcome (a), with the non-replicating fold-0 point disclosed.

Always report, on every fold evaluated: per-τ trade-off table (FP cases cleared / TP components lost /
case-level FN flips), cyst Dice (N = 98 and NaN-excluded), HEC K/M/T, Wilson CIs.

## 4. Both outcomes, written now (no post-hoc reinterpretation)

- **Fail** (predicted likely): §7.1 upgrades from "the reference method fails" to **"both the
  reference cross-scale method AND a dispersion-aware, cyst-tailored redesign fail, in the same
  coupled way"** — the agreement route is closed, and the strawman objection is answered directly
  (we built the serious version and it still fails, with a mechanism). One sentence into §7.1/§8.
- **Succeed**: honest **pivot**. Report the deterministic agreement filter as a genuine partial
  recovery (X% of FP removed at safe cost); **soften the headline** from "irreducible by image-only
  means" to "reducible in part by a deterministic ensemble-agreement filter, but not by any
  appearance-based discriminator." The Type X and metric-blind-spot contributions are unaffected.
  This would be a larger claim change than a minor pivot — accepted in advance, which is why it is
  pre-registered.

## 5. Scope discipline

This closes the **agreement** family. After it, the image-only coverage map is complete
(appearance §7.4 · input-scope §7.2 · training-objective §7.3 · uncertainty §8 · agreement = here).
No further "try one more variant" — that would be the endless-tuning trap this pre-registration exists
to prevent.

## 6. Logistics

CPU, folds 0/1/2, on existing predictions. Does not touch the running CV. Estimated ~hours.
Artifact: `agreement_corroboration_result.json` (TP/FP combo by τ, per-case operating points, all folds).
Feasibility note: if the fold-1/2 pipeline scratch dirs were cleaned, re-derive them with the
validated spot-check driver before evaluating — do not substitute a different path.

---
**SIGNED OFF AND LOCKED — claude.ai, 2026-08-11.** Amendments folded at sign-off: §1 τ in physical mm
+ cyst-only corroboration with declared justification; §2 pre-check demoted to descriptive (no
qualitative gate); §3 conservative TP-cost count + numeric HEC floor (−0.001) + folds-1/2 replication
gate. Criteria may not change after this line; results are reported under these rules regardless of
outcome.

---
**CLARIFICATION NOTE — claude.ai, 2026-08-11, recorded BEFORE any result existed** (verified: no
`agreement_corroboration_result.json`, empty run log at time of writing). These are interpretations of
the locked text where its instantiation was ambiguous across folds — not criteria changes:
1. **HEC floor is a per-fold delta criterion.** "Within −0.001 of the corrected baseline (0.9020)"
   means: within −0.001 of **that fold's own** corrected (Rule3+TypeX) baseline; the parenthetical
   0.9020 identifies fold-0's instance. Applying fold-0's absolute number to folds 1/2 (baselines
   0.8845 / 0.8836) would make replication arithmetically impossible and auto-force outcome (a),
   which is not what the gate is for. Each fold's baseline must be computed by the **same evaluator**
   as the filtered variants (self-calibration row required; a mismatch between this script's HEC and
   the canonical evaluator would otherwise silently consume the −0.001 budget).
2. **The ≥25% recovery gate is proportional per fold.** "≥ 25% of the 16 residual FP cases (≥ 4)" is
   fold-0's instance; replication on fold f requires clearing ≥ 25% of **fold f's** residual FP cases
   (fold-1: ≥ 7 of 25; fold-2: ≥ 6 of 21). This is stricter than reusing "≥ 4" — conservative
   direction, and the only self-consistent reading of "the same τ satisfies all of the above."
3. **The cost unit is CASES, as locked.** "Cyst-positive cases that lose ≥ 1 true-positive component"
   — a case losing several components counts once. Component totals are reported alongside but are
   not the criterion unit. (The first script draft compared FP *cases* against TP *components*; that
   deviation was caught in review before any result was produced and corrected.)
