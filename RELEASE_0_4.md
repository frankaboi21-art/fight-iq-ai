# Athlete development release — 0.4.0

Prepared October 19, 2026. As of October 20, purchase and deployment are on hold at the user's request while implementation, polish and functional verification continue. Do not request a database purchase again until the agreed scope and readiness checks are complete.

## Delivered in source

- Private athlete accounts, persistent profiles and explicit journal saving.
- Saved footage and manual coaching reports with integrity receipts and separate correction feedback.
- Practice tracking, evidence-linked reassessment, coverage dashboards and a rules-based personalized practice organizer.
- Athlete-authored tactical systems with an interactive decision explorer.
- Private opponent/style research notes, cited AI studies from selected confirmed footage, and revocable coach review/comment access.
- Resumable round reviews up to five minutes with progress, pause, cancellation, explicit retry and private temporary text results.
- Gym roles/invitations, opted-in self-training access, coach-authored shared plans, recipient outcomes and access/activity audit.
- Export, account recovery and deletion; durable usage allowances when PostgreSQL is configured.
- Updated branding and the founder's vision/roadmap.

## Database proposal

Render's account-specific New Postgres form quoted these settings on October 19, 2026:

| Setting | Prepared value |
| --- | --- |
| Name | fight-iq-training |
| Region | Oregon (same region as existing service) |
| PostgreSQL | 18 |
| Compute | 0.1 CPU / 256 MB, $6 per month |
| Storage | 1 GB, $0.30 per month |
| Storage autoscaling | Disabled |
| High availability | Disabled |
| Displayed recurring total | **$6.30 per month**, prorated by the second |

This is an additional database charge. Existing OpenAI usage, applicable taxes and other Render services are separate. No paid service should be created until the user approves this specific charge. The existing web service remains on its current plan. The database stores text records and hashes, not original videos or frame images.

After approval: create the database in the existing project/environment, restrict external database access, set its internal connection URL as the web service's `DATABASE_URL` securely, deploy the tested release and verify account persistence and access controls. Do not put the URL in Git, logs or chat. No OpenAI key rotation is required.

## Validation and release boundaries

Application tests cover account isolation, password recovery/session revocation, CSRF, report integrity, coach grants/revocation, reassessment constraints, deletion and production refusal to use ephemeral training storage. CI also exercises PostgreSQL 18. The owner authorized local synthetic browser testing on October 20. Desktop/mobile account, footage import/extraction, saving, practice tracking, multi-section processing and research checks have since run; camera and real-athlete coaching quality remain unverified. See VALIDATION.md for the evidence.

Real athlete footage quality evaluation still needs permissioned footage and qualified reviewers. The full long-term vision is the required launch scope. Consecutive sampled round review, cited AI scouting/style studies and gym collaboration are now implemented in working source. Continuous real-time computer vision, a professionally validated tactics library, advanced motion/pose measurements, richer adaptive plans and organizational reporting/integrations remain unfinished; they cannot be silently excluded from launch scope.

## October 24 additions

Round jobs require an athlete account, explicit frame permission and consent to temporary text storage. At most 30 sections plus three explicitly requested retries are allowed per job. A durable lease prevents concurrent round sections across instances; failures and interrupted leases never retry automatically. Defaults allow 30 round section attempts per service hour, 60/day and 36 per athlete/day, separately from short-clip allowances. Text results expire after seven days and are purged on startup/hourly while active and during relevant requests. Sleeping services purge on their next activity. No images or original video enter the database. Account exports include unexpired jobs and research; deletion cascades to both.

Research compares at most six eligible confirmed footage reviews from one discipline and research purpose. Every finding must cite a supplied moment; server code adds the original timestamp and evidence text. Source references and permission attestations are required, but ownership cannot be independently verified by this feature. Studies are AI drafts, use the written-coaching allowance, and do not feed personal practice plans. Changing source feedback invalidates advice; deleting a source deletes derived studies. No automatic downloading or opponent identification is performed.
