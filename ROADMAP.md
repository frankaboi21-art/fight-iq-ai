# Fight IQ AI development roadmap

This roadmap turns the [product vision](PRODUCT_VISION.md) into an implementation sequence. These are planned milestones, not delivered features or promised dates. Work should complete and validate the core training loop before expanding into scouting or real-time coaching.

**October 25, 2026 implementation status:** working source implements accounts/journals, outcome-prioritized weekly practice scheduling and linked reassessment, athlete-authored tactics, coach review/comments, resumable consecutive-section round reviews, cited AI scouting/style studies, and gym memberships, shared plans and access audits. Weekly scheduling adapts existing confirmed advice to reported outcomes and availability; it does not generate new drills. Purchase and deployment remain on hold until the full long-term scope is implemented, polished and validated. Continuous vision, AI-generated longitudinal coaching, organizational reporting/integrations and professionally reviewed tactical content remain unfinished. Local synthetic browser checks have started; they do not establish coaching accuracy. See [readiness evidence](VALIDATION.md).

## 1. Establish trustworthy footage coaching

**Athlete outcome:** reliably review a training exchange and leave with a specific, defensible practice task.

- Verify import, recording, playback, section selection, frame extraction, consent, retries initiated by the athlete, and result export on supported mobile and desktop browsers. Local browser testing with synthetic footage and test accounts was explicitly authorized on October 20; personal footage and camera use remain outside that test permission.
- Assemble a permissioned evaluation set across MMA/striking, boxing, and BJJ/wrestling, with coach-labelled moments, athlete identity by clothing/position, obscured views, and clips where no useful claim can be made.
- Evaluate timestamp grounding, athlete matching, unsupported claims, missed events, appropriate abstention, discipline accuracy, and usefulness of suggested drills. Report results per discipline and footage quality, including reviewer disagreement.
- Require evidence, uncertainty, a correction, and a measurable practice check for each actionable finding. Separate possible explanations from observed facts.
- Add Taekwondo with discipline-specific rules and coaching examples, then validate it against reviewed footage before presenting it as supported.
- Improve section navigation and sampling only where evaluation shows benefit. Measure processing time and cost before increasing coverage or promising whole-round analysis.

**Completion criteria:** supported browser workflows pass; a documented coach-reviewed evaluation establishes an initial quality baseline and release thresholds; errors and uncertain cases are understandable to athletes. Do not claim general accuracy before this evaluation exists.

## 2. Build athlete memory and measurable development

**Athlete outcome:** each session builds on the last instead of starting over.

- Introduce individual accounts, durable storage, isolated athlete records, and explicit controls for saving, exporting, and deleting history.
- Create editable profiles for discipline, experience, stance, goals, preferred style, training availability, and coach-provided context.
- Save consented reviews, athlete/coach corrections, selected priorities, assigned drills, and completion feedback. Saving original video should be a separate opt-in with defined retention.
- Build an adaptive development plan from confirmed observations and training feedback, with a small number of priorities and a reassessment date.
- Show progress only over comparable, reviewed sessions. Track observation coverage and uncertainty alongside changes; never turn missing data into a good score.
- Move usage limits to durable per-account storage and measure cost per useful review before broader access.

**Completion criteria:** an athlete can save a review, complete a practice task, revisit it in a later session, and see the evidence behind a changed recommendation. Account isolation and deletion are verified.

## 3. Teach tactical decision-making

**Athlete outcome:** understand what to try, what reactions to look for, and what to do next.

- Define a structured decision-tree format with situation, visible cue, athlete action, likely opponent responses, follow-up options, defensive exit, prerequisites, and ruleset.
- Start with coach-reviewed systems such as striking entry-to-exit sequences and grappling position-to-escape sequences.
- Link branches to reviewed footage and drills. Let athletes and coaches correct a branch and track the version used for training.
- Personalize trees to the athlete's confirmed skills and goals; frame opponent reactions as possibilities rather than predictions or guaranteed outcomes.

**Completion criteria:** athletes can navigate a complete coach-reviewed system, practice its branches, and relate it to evidence from their own sessions.

## 4. Expand analysis and coach collaboration

**Athlete and coach outcome:** review longer training histories together and plan focused preparation.

- Develop whole-round processing with background jobs, progress, cancellation, explicit sampling coverage, and cost controls. Evaluate motion/pose models where they demonstrably improve results.
- Add permissioned opponent scouting and professional style studies with source provenance and discipline context; avoid unsupported personality or capability claims.
- Build performance dashboards around validated observations and drill outcomes, with comparable time windows and visible coverage.
- Introduce coach annotations, shared plans, gym roles, athlete-controlled sharing, and auditable access.

**Completion criteria:** coaches can review and correct evidence, share a plan only with authorized people, and compare sessions without misleading aggregates. Longer-video processing meets documented reliability and cost targets.

## 5. Research real-time assistance and organizational tools

**Outcome:** extend the validated coaching system to live training and larger teams.

- Evaluate latency, frame quality, tracking stability, consent, interruption risks, and on-device versus hosted processing in controlled training settings.
- Start with post-round feedback or low-distraction drill cues; only expand live cues when user testing supports their usefulness.
- Build organizational integrations and reporting after permissions, retention, coach workflows, and measurement quality have been proven at smaller scale.

**Completion criteria:** live assistance has measured usefulness and reliability under its advertised conditions, and organizational access preserves athlete control over footage and records.

## Measures of progress

Use these as proposed product measures; the beta does not yet collect them automatically. Define thresholds from initial evaluation rather than inventing performance claims.

| Measure | What it answers |
| --- | --- |
| Coach-confirmed, evidence-supported findings | Is the advice grounded and useful? |
| Unsupported claims and correct abstentions | Does the system recognize its limits? |
| Completed practice tasks followed by reassessment | Does analysis become training action? |
| Repeated, comparable observations across sessions | Can an athlete and coach verify progress? |
| Successful reviews, latency, and cost per review | Can athletes depend on the service? |
| Athlete and coach corrections | Where does the system need to improve? |

Do not use a composite Fight IQ score as the sole success measure. The product's purpose is to help athletes make better training decisions and verify improvement over time.
