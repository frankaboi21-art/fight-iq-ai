# Fight IQ AI readiness record

Updated October 29, 2026. Paid hosting and deployment are on hold at the owner's request while implementation, polish and functional verification continue. A green code test suite alone does not mean the product vision is fully implemented or the coaching is validated.

## Working source versus remaining scope

| Product area | Implemented foundation | Required before claiming the full capability |
| --- | --- | --- |
| Footage coaching | Record/import controls, short-section reviews, consecutive round processing up to five minutes, progress/pause/resume/cancel, temporary text results and evidence index | Wider device/codec tests, permissioned real footage, coach-reviewed accuracy and cost/latency evaluation; continuous motion/identity tracking remains unimplemented |
| Athlete development | Private profiles, saved text reviews, outcome-prioritized weekly practice outlines, explicit timing, source-linked reassessment, coverage dashboard | Broader end-to-end user testing; AI-generated longitudinal coaching and measured usefulness |
| Tactical education | Athlete-authored decision systems, linked journal evidence and branch explorer | Professionally reviewed content, discipline-specific evaluation and more complete systems |
| Scouting/style study | Private notes plus AI comparison of up to six explicitly selected, confirmed footage reviews; server-checked citations, source references, permissions attestation and source-change invalidation | Real-provider and coach-reviewed usefulness evaluation; these are studies of supplied evidence, not autonomous web scouting or athlete identification |
| Coach collaboration | Revocable direct access/comments, gym roles/invitations/sharing, shared plans/audit, gym-owner qualification checks and attributed item decisions/corrections; optional coach-supported-only scheduling | A real qualified reviewer (owner will choose later), permissioned evaluation, organizational reporting/integrations; gym attestations are not independent certification |
| Real-time assistance | Bounded near-live sampled windows, actual timestamps, stop/hidden-tab cleanup, visible delay, quotas and optional journal save | Real camera/device and provider latency checks, continuous tracking, controlled athlete evaluation and measured usefulness; current mode is delayed visual review |
| Discipline coverage | Existing MMA/striking/boxing/grappling beta choices; Taekwondo profiles, notes and tactical systems | Taekwondo automated review and evidence-based validation of each supported discipline |

## Verification evidence

- Baseline release commit `1220055`: 82 API/domain tests passed in CI across SQLite and PostgreSQL 18.
- The baseline also passed JavaScript syntax and DOM logic checks for safe text rendering, explicit AI context application, signed snapshot saving, tactical branching and stale-footage prevention.
- On October 20 the owner authorized local browser tests with synthetic footage and test accounts. Camera use and personal footage are not part of that permission. Browser verification is in progress.
- October 24 working source: 83 local API/domain tests passed (SQLite). New coverage includes round interruption/cancellation, frame non-retention, explicit retry, privacy, account deletion and research citation/source checks. PostgreSQL CI must be rerun for this source revision.
- Local browser checks passed: test account creation and persistence across service restart; six-second MP4 import/30-frame extraction; saving footage and corner reviews; confirming advice; recording practice; mobile layout at 390×844 without page overflow; a 21-second round reviewed in three consecutive seven-second sections; research generation/storage with deterministic fixture responses. Browser console showed no errors in the checked round flow.
- Fixed garbled UI symbols, password whitespace handling and reassessment priority selection. Browser checks use synthetic fixtures and cannot establish AI coaching quality.
- Round/research checkpoint `4cdaa94` passed 118 CI checks across SQLite and PostgreSQL 18, plus JavaScript syntax and DOM checks.
- Gym workflow checks cover invitation acceptance, private-by-default journals, scoped coaching access, revocation, research exclusion, recipient-only outcomes, source deletion and owner-account cascading deletion. Local browser creation, plan assignment and recipient feedback succeeded with a synthetic gym/account. Updated full-suite and PostgreSQL results are recorded in the draft PR checks.
- Gym checkpoint `7627c5f` passed 128 CI checks across SQLite and PostgreSQL 18, plus JavaScript syntax and DOM checks.
- October 25 weekly planner: 24 focused training/development tests passed locally. New cases cover unresolved-outcome priority, full-drill budgets, exact versus ambiguous written durations, explicit timing overrides, source invalidation, duplicate completion and discipline/research isolation. Synthetic browser checks confirmed changing a drill from five to seven planned minutes rebuilds the week from 24 to 30 minutes without changing actual practice counts or source instructions. Desktop and 390×844 layouts fit without horizontal page overflow.
- The complete local suite now passes 96 tests. Extended DOM checks pass for weekly outline rendering, safe text, JSON export content, and numeric planning-time submission without marking practice complete. Browser console checks are clear. The in-app browser download-event observer timed out, but the actual downloaded `fight-iq-weekly-outline.json` was verified in Downloads with the expected format, snapshot flag and updated 30-minute schedule. PostgreSQL CI for this checkpoint is tracked in PR #3.
- Weekly planner checkpoint `511bfb7` passed 140 CI tests across SQLite and PostgreSQL 18, plus JavaScript syntax and extended DOM checks (run `40255012785`).
- October 29 live/coach source: 108 local backend tests passed. New cases cover actual timestamps, session ownership, context mismatch, malformed/stale/duplicate frames, bounded starts/attempts, lease cleanup and late-result discard; qualification permissions/scope, source attestation, corrections, source invalidation, sharing revocation and deletion. Training/live DOM checks and JavaScript syntax checks pass, including decoder failure and late camera-permission cleanup using mocks.
- Synthetic browser checks verified a sampled four-second window, explicit journal saving, a gym-owner qualification fixture, attributed coach correction and exclusion from weekly plans. The coach-only profile also withholds unreviewed drills. All qualification/review content is labelled synthetic; no actual credential or athlete was evaluated. Final mobile/live evidence and PostgreSQL results are recorded with the draft PR checkpoint.
- October 29 final browser pass: local playback produced 18 sampled frames across 4.1 seconds, with a fixture abstention and automatic capture stop. Manual Stop also succeeded. At a 390×844 viewport, live controls/results fit without horizontal page overflow; console warnings/errors were empty. Screenshots were saved locally. No real camera, microphone, athlete footage or paid provider request was used.
- Synthetic blank-image abstention was checked during the footage release. This is not a real-athlete coaching accuracy evaluation.
- Real athlete evaluation requires footage supplied with permission and qualified reviewer judgments; no evaluation data or accuracy figures should be invented.

## Completion gates

1. The owner confirmed the entire long-term vision is the launch scope on October 20. Map every promised feature to a working user flow and tests; do not quietly defer features to an athlete-only launch.
2. Pass current API, database and interface checks, including persistence across restarts, account isolation, sharing/revocation, recovery, export/deletion and error handling.
3. Exercise supported desktop/mobile browser workflows with synthetic media first, then permissioned training clips. Confirm accessibility, layout and recovery from media/provider failures.
4. Evaluate grounded findings, athlete matching, correct abstention, discipline relevance and practical usefulness against coach-reviewed footage; report coverage and limitations.
5. Resolve known blockers and document any intentionally deferred capability without marketing it as available.
6. Only then revisit hosting cost approval and production deployment. Purchase approval remains a separate user decision.
