# Fight IQ AI

**Train with intelligence. Fight with purpose. Evolve with every session.**

Our goal is to make high-quality combat sports intelligence, education, and performance analysis more accessible, personalized, and measurable. The [product vision](PRODUCT_VISION.md) defines that destination; the [development roadmap](ROADMAP.md) sets the implementation sequence and validation criteria. The capabilities below describe the current beta.

An invite-only martial-arts coaching beta with a footage lab and manual session review. Record or choose video locally, inspect short exchanges, and request evidence-linked coaching for MMA, boxing, Muay Thai, kickboxing, BJJ or wrestling.

## What works

- Private athlete accounts with password sign-in, one-time recovery codes, profile preferences and explicit text-review saving.
- A persistent journal for training reviews, opponent notes and style studies; scouting does not feed the athlete's personal practice plan.
- A rules-based practice organizer from confirmed reviews, with completion notes and reassessment linked to later confirmed evidence in the same discipline and setting.
- Progress coverage, self-reported outcomes, athlete-authored tactical decision trees, and revocable coach access to self-training reviews and comments.
- Account export and deletion. Original videos and extracted frames are never stored in the training database.
- Camera recording (video only) and local video import, with playback, slow motion and FPS-based stepping.
- Five sampled frames per second for a selected 1–10-second section; up to 50 frames per review. Longer videos can be reviewed section by section.
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

## Athlete development

Create an account after unlocking beta access, using a unique username and a password of 15–128 characters. Save the recovery code in a password manager: there is no email reset. Passwords use scrypt; recovery codes and session tokens are stored as hashes. Account sessions last seven days. Resetting a password rotates the recovery code and revokes existing account sessions. Beta access remains separately required for AI requests.

Saving a review is a separate action with a purpose, training setting, date and duration. AI reports and manual assessments carry integrity receipts; altering the generated report invalidates saving it as that report. Corrections are recorded separately, preserving the source. Save a written note for observations outside an AI review. Only confirmed self-training reviews in the athlete's primary discipline supply practice tasks; uncertain footage never supplies tasks. The organizer prioritizes recent outstanding drills, groups duplicate names and fits them to the chosen time budget. It does not make a fresh AI diagnosis or claim validated progress.

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
```

Tests mock OpenAI; they never spend API credits. Before a release, browser verification should cover empty/partial/complete assessments, repeat observations, sample data, access, coaching output, mobile layout, and errors. A live AI test should be a deliberate separate check.

Training tests run against SQLite locally and additionally against PostgreSQL 18 in CI. To test a disposable local PostgreSQL database, set `TRAINING_TEST_POSTGRES_URL` to that test database before running pytest. **The training fixture deletes all athletes and usage attempts in that test database. Never point it at production.**

CI also runs `tests/training_ui.cjs` with Node 26 and `jsdom@30.1.3`. This checks DOM logic for safe profile rendering, explicit context application, saving signed snapshots, tactical branches and stale-footage protection. It uses mocked HTTP and no browser/camera or layout rendering. For a local run, install that test dependency under `.test-deps` and set `NODE_PATH` to `.test-deps/node_modules` before invoking the test.

## API

- `GET /api/v1/health`: service and configuration status; no secrets.
- `GET /api/v1/mistakes`: observation catalogue and pillar identifiers.
- `POST /api/v1/analysis`: validated `mistakes` and `reviewed_pillars`.
- `GET /api/v1/analysis/demo`: clearly labelled sample assessment.
- `GET/POST/DELETE /api/v1/session`: inspect, unlock, or lock beta access.
- `POST /api/v1/video/review`: authenticated, consented frame sequence and athlete context; returns an evidence-linked `review`.
- `POST /api/v1/ai/coach`: authenticated session review, recomputed server-side. Returns a structured `plan`.
- `/api/v1/training`: account registration/login/recovery/logout, profile, journal entries, feedback, practice outcomes, development summary, tactical systems, coach grants/comments, export and account deletion. These use a separate athlete session cookie and never accept video/image uploads.
- `WS /ws/live/{session_id}`: bounded, validated observation updates.

Session mutations and coaching require `X-FightIQ-Client: web`; browser origins must match the canonical app origin. Invalid, expired, or absent sessions cannot call OpenAI.

## Product boundaries

Scores are provisional estimates based on manual observations. The weights and grade thresholds have not been clinically or competitively validated. They do not measure overall fighting ability. Footage reviews inspect sampled still frames from the selected section, not continuous video or audio. The app does not diagnose injuries or replace a qualified coach.

AI requests still use a shared beta invitation code. Individual athlete accounts persist only explicitly saved text records; unsaved reviews are lost when the tab closes or refreshes. The usage ledger retains only hashes, event types and timestamps for 24 hours. Saved athlete records persist until deleted. AI requests send selected observations or consented footage frames and context to OpenAI with response storage disabled. Applying a saved profile/practice focus copies details into visible form fields; it does not send the journal to AI automatically.
