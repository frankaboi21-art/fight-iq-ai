# Fight IQ AI

An invite-only martial-arts coaching beta with a footage lab and manual session review. Record or choose video locally, inspect short exchanges, and request evidence-linked coaching for MMA, boxing, Muay Thai, kickboxing, BJJ or wrestling.

## What works

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

The current request ledger is SQLite on the service filesystem. It survives process restarts while that filesystem remains, but Render's free disk is ephemeral: deploys or instance replacement can reset it. Run one instance and one worker for this beta. It is not a durable financial cap. Monitor provider usage and budget alerts; move counters to shared persistent storage before scaling or promising durable per-account quotas.

## Verification

```sh
python -m pytest -q
node --check static/app.js
node --check static/video.js
```

Tests mock OpenAI; they never spend API credits. Before a release, browser verification should cover empty/partial/complete assessments, repeat observations, sample data, access, coaching output, mobile layout, and errors. A live AI test should be a deliberate separate check.

## API

- `GET /api/v1/health`: service and configuration status; no secrets.
- `GET /api/v1/mistakes`: observation catalogue and pillar identifiers.
- `POST /api/v1/analysis`: validated `mistakes` and `reviewed_pillars`.
- `GET /api/v1/analysis/demo`: clearly labelled sample assessment.
- `GET/POST/DELETE /api/v1/session`: inspect, unlock, or lock beta access.
- `POST /api/v1/video/review`: authenticated, consented frame sequence and athlete context; returns an evidence-linked `review`.
- `POST /api/v1/ai/coach`: authenticated session review, recomputed server-side. Returns a structured `plan`.
- `WS /ws/live/{session_id}`: bounded, validated observation updates.

Session mutations and coaching require `X-FightIQ-Client: web`; browser origins must match the canonical app origin. Invalid, expired, or absent sessions cannot call OpenAI.

## Product boundaries

Scores are provisional estimates based on manual observations. The weights and grade thresholds have not been clinically or competitively validated. They do not measure overall fighting ability. Footage reviews inspect sampled still frames from the selected section, not continuous video or audio. The app does not diagnose injuries or replace a qualified coach.

This release uses one shared beta invitation code, not individual user accounts. Sessions and coaching plans are not saved to a user database. Refreshing or closing the tab loses the current review; download notes to keep the generated plan. The usage ledger retains only hashes, event types, and timestamps for 24 hours, not training notes. AI requests send the selected observations or explicitly consented footage frames and context to OpenAI with response storage disabled.
