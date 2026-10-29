# Fight IQ AI

**Train with intelligence. Fight with purpose. Evolve with every session.**

Our goal is to make high-quality combat sports intelligence, education, and performance analysis more accessible, personalized, and measurable. The [product vision](PRODUCT_VISION.md) defines that destination; the [development roadmap](ROADMAP.md) sets the implementation sequence and validation criteria. The capabilities below describe the current beta.

An invite-only martial-arts coaching beta with a footage lab and manual session review. Record or choose video locally, inspect short exchanges, and request evidence-linked coaching for MMA, boxing, Muay Thai, kickboxing, BJJ or wrestling.

## What works

- Private athlete accounts with password sign-in, one-time recovery codes, profile preferences and explicit text-review saving.
- A persistent journal for training reviews, opponent notes and style studies; scouting does not feed the athlete's personal practice plan.
- A rules-based practice organizer from confirmed reviews, with completion notes and reassessment linked to later confirmed evidence in the same discipline and setting.
- Progress coverage, self-reported outcomes, athlete-authored tactical decision trees, and revocable coach access to self-training reviews and comments.
- Gym workspaces with owner/coach/athlete roles, accepted invitations, athlete-controlled self-training sharing, coach-authored plans, recipient feedback and access/activity records. Joining a gym does not automatically share a journal.
- Near-live practice from a camera or local playback: four-second sampled windows, explicit stop, visible processing delay, and optional text saving.
- Attributed coach decisions on individual findings/drills, discipline qualifications checked by a gym owner, correction history, and an optional coach-supported-only weekly plan.
- Account export and deletion. Original videos and extracted frames are never stored in the training database.
- Camera recording (video only) and local video import, with playback, slow motion and FPS-based stepping.
- Five sampled frames per second for a selected 1–10-second section; up to 50 frames per review. Longer videos can be reviewed section by section.
- Consecutive-section reviews covering up to five minutes, with background section processing, progress, pause/resume, cancellation, explicit retries and a bounded evidence index. Temporary text results expire after seven days; images are never persisted.
- AI scouting and style studies from up to six chosen, confirmed footage reviews, with server-resolved citations and invalidation when source evidence changes. These drafts require coach review.
- Athlete selection by clothing/position, discipline and experience context, cited evidence frames, strengths/corrections, skills to explore, and practice blocks with success checks.
- A server-validated evidence timeline: timestamps come from supplied frames, not invented model times. Unusable footage or uncertain athlete matching suppresses personalized findings.

- Round and repetition-aware observations with input validation.
- Explicit review coverage: unreviewed pillars stay unassessed. An overall estimate appears only when all six pillars have been reviewed.
- Structured coaching: reported observations, one correction, three tactical steps, two drills, and a corner cue.
- Responsive, accessible dashboard with labelled controls, keyboard focus, error recovery, copy and download.
- AI coaching behind a beta code, signed HttpOnly session cookies, origin checks, atomic request allowances, bounded request/output sizes, timeouts, and no automatic provider retries.

## Local development

Use Python 3.12 or later:

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --ws-max-size 32768
```

Configure `.env` using `.env.example`. Keep all real credentials out of Git. The server reads the OpenAI key; the browser never receives it. Reuse the key already configured for this app.

AI coaching is disabled until `BETA_ACCESS_CODE` contains a random secret at least 20 characters long. Use a password manager to generate a unique code, save it securely, and share it only with invited testers. The access code is separate from the OpenAI API key. Rotating the code invalidates existing sessions.

## Configuration

| Variable | Purpose / default |
| --- | --- |
| `OPENAI_API_KEY` | Existing OpenAI key, server-only |
| `OPENAI_MODEL` | `gpt-6-astra` |
| `BETA_ACCESS_CODE` | Required random beta invitation code, at least 20 characters |
| `ENVIRONMENT` | `production` enables Secure cookies; local default is `development` |
| `PUBLIC_ORIGIN` | Optional canonical origin such as `https://fight-iq-ai.onrender.com` |
| `RENDER_EXTERNAL_URL` | Render's automatic canonical URL; used if `PUBLIC_ORIGIN` is unset |
| `DATABASE_URL` | Persistent PostgreSQL connection string; required for saved accounts in production |
| `TRAINING_DB_PATH` | `.data/training.sqlite3`, development/test fallback only |
| `ROUND_HOURLY_LIMIT` / `ROUND_DAILY_LIMIT` | Shared longer-round section attempts: 30/hour and 60/day by default; separate from short-clip limits |
| `LIVE_HOURLY_LIMIT` / `LIVE_DAILY_LIMIT` | Shared near-live attempts: 12/hour and 24/day by default; six per athlete per rolling 15 minutes |
| `CORS_ORIGINS` | Leave empty for the same-origin deployed frontend |
| `SESSION_HOURS` | 8, configurable from 1 to 24 |
| `COACH_HOURLY_LIMIT` | 10 attempted provider requests across the service |
| `COACH_DAILY_LIMIT` | 30 attempted provider requests across the service |
| `USAGE_DB_PATH` | `.data/usage.sqlite3` |

Written-coaching limits: 3 coaching attempts per session per rolling 15 minutes; 2 simultaneous coaching calls per process; 8 sign-in attempts per source address per 15 minutes and 100 sign-in attempts globally. Failed provider requests still consume allowances. Signing in again cannot bypass the shared hourly/daily limits. These are request counts, not dollar limits.

## Footage review

The original video is loaded as a local browser blob. It is not uploaded to the app. The browser extracts JPEGs from the selected section at 5 fps, with a maximum long edge of 768 px. Only when the user checks permission/processing consent and requests a review are these frames and athlete context sent through the authenticated server to OpenAI. No audio is captured or submitted. Response storage is disabled (`store=False`); this does not imply a zero-retention provider policy.

Videos up to 250 MB and four hours can be opened if their codecs are supported by the browser; MP4/H.264 is a useful compatibility choice. Camera recording stops at three minutes or 200 MB. Camera access requires HTTPS or localhost and browser permission. Users should save camera recordings before refreshing. Native media support varies by browser/device.

AI does **not** inspect every original video frame. Each request covers only the selected 1–10 seconds at 5 fps. Fast strikes, occluded grips and transitions may be missed. The player steps by the selected source FPS and is approximate for variable-frame-rate footage. Confidence is the model's assessment, not a calibrated accuracy guarantee. No force, exact biomechanics, injury diagnosis or fighter ranking is inferred.

Video requests have a 6.1 MB body cap, authenticated before body buffering, at most 50 JPEGs (120,000 characters each), decoded dimension validation, ordered timestamp checks, required consent, one concurrent provider call, an 85-second server deadline, and no automatic retries. Allowances are separate from written coaching: two attempts per session per rolling 15 minutes, three across the service per rolling hour and ten per rolling day. Provider failures count; malformed inputs do not. The same ephemeral-storage limitations below apply.

## Render deployment

The `Dockerfile` and `render.yaml` describe a single free web service. Keep the existing service and its OpenAI key. Set `BETA_ACCESS_CODE` securely in Render's Environment panel before deploying this release. Use `/api/v1/health` as the health check. The frontend is served by the same service; no extra API host or permissive CORS configuration is needed.

`render.yaml` does not update a manually configured service automatically. Changes to secrets on an existing service must be applied in the dashboard. Free instances sleep when idle and may take time to wake.

With `DATABASE_URL`, accounts, profiles, saved text reviews, practice outcomes, tactical systems, coach grants/comments and request allowances use PostgreSQL. Allowance reservations are serialized with a database advisory lock; signed-in athletes retain the same allowance identity across beta unlocks. Without it, only the previous beta features run in production: saved-account endpoints refuse to use ephemeral disk. The original SQLite usage ledger remains a fallback and can reset when Render replaces its filesystem. These request counts are not a financial cap. Continue running one worker for the current AI concurrency limits.

## Near-live practice and human review

Live practice samples approximately five frames per second, preserving actual browser capture timestamps. Each four-second window contains 10–25 frames; interrupted, stale or unreadable windows are rejected. Only one live provider request runs at a time, with a database lease across instances, an 85-second deadline and no automatic retry. A session lasts at most three minutes and six windows. Twenty session starts per athlete per ten minutes bounds temporary state. Capture pauses during processing and leaves five seconds between windows to read feedback; Stop gives the athlete more time. Hiding the tab, leaving the page or signing out stops capture. Late results after stopping are discarded. Already submitted work may still consume provider usage.

No microphone, original video recording, automatic journal saving or continuous pose tracking is used by this mode. Temporary session context is cleared on Stop; remaining temporary records are purged after ten minutes on the next minute cleanup tick while the service is active, or on its next wake/start. Frame images and unsaved results are not persisted. Saving a window uses the ordinary consented journal workflow. The displayed delay describes completed capture, not the athlete's current pose. Actual device performance, provider latency and coaching quality still require evaluation.

A gym owner can record checking another active coach's qualification evidence for a named discipline, with a reference and expiry/review date. This is a gym attestation, not independent Fight IQ certification; owners cannot verify themselves. An eligible coach can review an athlete-confirmed, shared self-training record, attest to checking the original source, and support, correct, reject or mark an individual finding/drill uncertain. Corrections require practice instructions and a visible success check. Original AI advice stays intact, with attributed review history alongside it.

Current support requires the same source and current qualification. Changed sources or expired/replaced/revoked qualifications invalidate support. A coach objection continues to hold the original drill out of weekly plans until resolved, even after a credential is revoked. Corrected instructions are displayed separately and are not silently substituted into the schedule. The profile can require current coach support for every scheduled drill. Athlete confirmation or an ordinary comment never counts as coach validation. Account archives include human review records. A real qualified reviewer will be selected by the owner later; synthetic test credentials establish no real expertise or accuracy.

## Athlete development

Create an account after unlocking beta access, using a unique username and a password of 15–128 characters. Save the recovery code in a password manager: there is no email reset. Passwords use scrypt; recovery codes and session tokens are stored as hashes. Account sessions last seven days. Resetting a password rotates the recovery code and revokes existing account sessions. Beta access remains separately required for AI requests.

Saving a review is a separate action with a purpose, training setting, date and duration. AI reports and manual assessments carry integrity receipts; altering the generated report invalidates saving it as that report. Corrections are recorded separately, preserving the source. Save a written note for observations outside an AI review. Only confirmed self-training reviews in the athlete's primary discipline supply practice tasks; uncertain footage never supplies tasks. The latest performed session governs each duplicate drill name. Needs-work and unchanged reassessments take priority, followed by practiced drills awaiting reassessment, then new drills; recency breaks ties. Improving drills leave the active plan with a link to their reassessment evidence. This organizes existing advice; it does not make a fresh AI diagnosis or claim validated progress.

The weekly outline uses the profile's session count and time budget, schedules at most three full drills per session, and suggests checking evidence again in seven days. It never silently shortens drills or invents time for ambiguous round/repetition descriptions. Athletes can record a 1–60 minute planning duration separately from the original report, ideally agreed with their coach. Drills that cannot fit remain visible with a reason. Session slots do not record completion, increase intensity, or prescribe additional exercises. Feedback, timing and availability changes rebuild the live outline; the downloadable JSON is a dated snapshot. The organizer makes no provider calls. Applying priorities to the next AI review copies the chosen tasks, checks and self-reported outcomes into visible fields for review before submission.

Reassessment requires a later, confirmed self-training record in the same discipline and setting. Outcomes are explicitly self-reported. Removing or unconfirming linked evidence resets its associated reassessment result. Coverage tables distinguish sampled video seconds, manually reviewed pillars and logged session minutes; the app does not aggregate those into a fighter ranking.

Tactical systems are athlete-authored, versioned by saving a new copy, and can reference a journal entry. The explorer presents a situation, cue, action, possible reactions, follow-ups and defensive exits. They are training hypotheses, not a coach-validated library or guaranteed predictions. Taekwondo is supported for profiles, written records and tactical systems; automated Taekwondo footage review remains pending validation.

Coach access is granted to an exact existing username. It includes all present and future self-training entries and their text notes; it excludes the private profile, scouting and style research. Coaches can comment but cannot confirm, edit or delete an athlete's records. Revocation prevents future reads/comments; it cannot erase copies a recipient already made. Granting access sends no message and does not verify coaching credentials.

Account exports contain profile, saved entries, practice results, tactical systems and comments. Deleting an account removes its active records, sessions, grants and authored comments through database cascades. Managed database backups follow provider retention and are not erased immediately by an account deletion. Use the app's export before deletion when a personal archive is needed.

PostgreSQL schema creation is idempotent and protected by a schema advisory lock. Production never falls back to the development SQLite training file. Set the database URL through Render's secret environment settings, not in source control. See [release setup](RELEASE_0_4.md) for the prepared deployment and pending approval.

## Verification

```sh
python -m pytest -q
node --check static/app.js
node --check static/video.js
node --check static/training.js
node --check static/live.js
```

Tests mock OpenAI; they never spend API credits. Before a release, browser verification should cover empty/partial/complete assessments, repeat observations, sample data, access, coaching output, mobile layout, and errors. A live AI test should be a deliberate separate check.

Training tests run against SQLite locally and additionally against PostgreSQL 18 in CI. To test a disposable local PostgreSQL database, set `TRAINING_TEST_POSTGRES_URL` to that test database before running pytest. **The training fixture deletes all athletes and usage attempts in that test database. Never point it at production.**

CI also runs `tests/training_ui.cjs` with Node 26 and `jsdom@30.1.3`. This checks DOM logic for safe profile rendering, explicit context application, saving signed snapshots, tactical branches, stale-footage protection, weekly outlines/JSON export content and explicit planning-time submission. It uses mocked HTTP and no browser/camera or layout rendering. For a local run, install that test dependency under `.test-deps` and set `NODE_PATH` to `.test-deps/node_modules` before invoking the test.

`tests/live_ui.cjs` uses synthetic media APIs to check bounded capture, stop/hidden-tab behavior, late result and camera-permission cleanup, and decoder failure. It never opens a camera or calls a provider.

## API

- `GET /api/v1/health`: service and configuration status; no secrets.
- `GET /api/v1/mistakes`: observation catalogue and pillar identifiers.
- `POST /api/v1/analysis`: validated `mistakes` and `reviewed_pillars`.
- `GET /api/v1/analysis/demo`: clearly labelled sample assessment.
- `GET/POST/DELETE /api/v1/session`: inspect, unlock, or lock beta access.
- `POST /api/v1/video/review`: authenticated, consented frame sequence and athlete context; returns an evidence-linked `review`.
- `POST /api/v1/ai/coach`: authenticated session review, recomputed server-side. Returns a structured `plan`.
- `/api/v1/training`: account registration/login/recovery/logout, profile, journal entries, feedback, practice outcomes, development summary, tactical systems, coach grants/comments, export and account deletion. These use a separate athlete session cookie and never accept video/image uploads.
- `/api/v1/rounds`: create/list/read/delete private temporary round jobs, submit the next section, and cancel. Athlete account plus beta access is required to submit provider work. Completed text survives reloads; reselect the identical source file to resume. One section is processed globally at a time using a database lease, with up to three explicit extra attempts per round. Failed provider calls count toward allowances. Expired jobs are purged on service startup, hourly while active, and during job listing/creation; a sleeping service purges when it next runs. Provider calls already started can still consume usage after cancellation.
- `/api/v1/research`: generate/list/delete private cited studies from confirmed research footage entries. Uses the written-coaching allowance. Chosen review text, references and corrections are sent with explicit consent; no third-party URLs are fetched. Deleting source entries deletes their derived studies; correcting/unconfirming sources hides stale advice.
- `/api/v1/gyms`: create/list/manage gym workspaces and invitations, accept/leave memberships, choose journal sharing, review shared self-training, assign plans and record recipient feedback. Owners manage membership; active coaches see only opted-in self-training journals. Research/profile data stays private. Revoking gym sharing does not revoke separately granted direct-coach access. Leaving/removal deletes plans assigned to that member; deleting the owner account deletes owned gyms and their plans. Audit views show the latest 100 events to owners and relevant personal events to other members; repeated review-access events are coalesced for one minute.
- `/api/v1/live`: start/stop an owned temporary live session and submit fresh sampled windows; requires an athlete account, with beta access for starting/provider work.
- `/api/v1/validation`: gym qualification checks/revocation and attributed item-level human decisions on shared self-training records.
- `WS /ws/live/{session_id}`: bounded, validated manual observation updates; separate from the sampled-video live practice feature.

Session mutations and coaching require `X-FightIQ-Client: web`; browser origins must match the canonical app origin. Invalid, expired, or absent sessions cannot call OpenAI.

## Product boundaries

Scores are provisional estimates based on manual observations. The weights and grade thresholds have not been clinically or competitively validated. They do not measure overall fighting ability. Footage reviews inspect sampled still frames from the selected section, not continuous video or audio. The app does not diagnose injuries or replace a qualified coach.

AI requests still use a shared beta invitation code. Individual athlete accounts persist explicitly saved text records and consented temporary round results. Unsaved short-section reviews are lost when the tab closes or refreshes. The usage ledger retains only hashes, event types and timestamps for 24 hours. Saved athlete records and studies persist until deleted. AI requests send selected observations, research evidence, or consented footage frames and context to OpenAI with response storage disabled. Applying a saved profile/practice focus copies details into visible form fields; it does not send the journal to AI automatically.

For isolated browser verification, run `python -m uvicorn tests.preview_app:app --host 127.0.0.1 --port 8007`. This explicit test entry point uses deterministic synthetic provider results, a separate `.data/browser-preview` database and the non-secret test invitation `synthetic-browser-test-code`. Never deploy this entry point. Synthetic interface checks and real athlete coaching evaluation are separate; see [VALIDATION.md](VALIDATION.md) for the remaining full-vision launch gates.
