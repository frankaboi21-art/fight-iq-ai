# Fight IQ AI readiness record

Updated October 24, 2026. Paid hosting and deployment are on hold at the owner's request while implementation, polish and functional verification continue. A green code test suite alone does not mean the product vision is fully implemented or the coaching is validated.

## Working source versus remaining scope

| Product area | Implemented foundation | Required before claiming the full capability |
| --- | --- | --- |
| Footage coaching | Record/import controls, short-section reviews, consecutive round processing up to five minutes, progress/pause/resume/cancel, temporary text results and evidence index | Wider device/codec tests, permissioned real footage, coach-reviewed accuracy and cost/latency evaluation; continuous motion/identity tracking remains unimplemented |
| Athlete development | Private profiles, saved text reviews, confirmed-review practice organizer, reassessment, coverage dashboard | Complete end-to-end user testing; richer adaptive plans and measured longitudinal usefulness |
| Tactical education | Athlete-authored decision systems, linked journal evidence and branch explorer | Professionally reviewed content, discipline-specific evaluation and more complete systems |
| Scouting/style study | Private notes plus AI comparison of up to six explicitly selected, confirmed footage reviews; server-checked citations, source references, permissions attestation and source-change invalidation | Real-provider and coach-reviewed usefulness evaluation; these are studies of supplied evidence, not autonomous web scouting or athlete identification |
| Coach collaboration | Revocable access to self-training reviews and attributed comments | Gym roles, team administration, shared planning, access audit trail and organizational workflows |
| Real-time assistance | No continuous real-time analysis | Implement and evaluate latency, tracking, feedback usefulness and appropriate live-training use |
| Discipline coverage | Existing MMA/striking/boxing/grappling beta choices; Taekwondo profiles, notes and tactical systems | Taekwondo automated review and evidence-based validation of each supported discipline |

## Verification evidence

- Baseline release commit `1220055`: 82 API/domain tests passed in CI across SQLite and PostgreSQL 18.
- The baseline also passed JavaScript syntax and DOM logic checks for safe text rendering, explicit AI context application, signed snapshot saving, tactical branching and stale-footage prevention.
- On October 20 the owner authorized local browser tests with synthetic footage and test accounts. Camera use and personal footage are not part of that permission. Browser verification is in progress.
- October 24 working source: 83 local API/domain tests passed (SQLite). New coverage includes round interruption/cancellation, frame non-retention, explicit retry, privacy, account deletion and research citation/source checks. PostgreSQL CI must be rerun for this source revision.
- Local browser checks passed: test account creation and persistence across service restart; six-second MP4 import/30-frame extraction; saving footage and corner reviews; confirming advice; recording practice; mobile layout at 390×844 without page overflow; a 21-second round reviewed in three consecutive seven-second sections; research generation/storage with deterministic fixture responses. Browser console showed no errors in the checked round flow.
- Fixed garbled UI symbols, password whitespace handling and reassessment priority selection. Browser checks use synthetic fixtures and cannot establish AI coaching quality.
- Synthetic blank-image abstention was checked during the footage release. This is not a real-athlete coaching accuracy evaluation.
- Real athlete evaluation requires footage supplied with permission and qualified reviewer judgments; no evaluation data or accuracy figures should be invented.

## Completion gates

1. The owner confirmed the entire long-term vision is the launch scope on October 20. Map every promised feature to a working user flow and tests; do not quietly defer features to an athlete-only launch.
2. Pass current API, database and interface checks, including persistence across restarts, account isolation, sharing/revocation, recovery, export/deletion and error handling.
3. Exercise supported desktop/mobile browser workflows with synthetic media first, then permissioned training clips. Confirm accessibility, layout and recovery from media/provider failures.
4. Evaluate grounded findings, athlete matching, correct abstention, discipline relevance and practical usefulness against coach-reviewed footage; report coverage and limitations.
5. Resolve known blockers and document any intentionally deferred capability without marketing it as available.
6. Only then revisit hosting cost approval and production deployment. Purchase approval remains a separate user decision.
