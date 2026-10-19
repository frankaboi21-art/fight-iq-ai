# Athlete development release — 0.4.0

Prepared October 19, 2026. Deployment is pending database purchase approval and configuration.

## Delivered in source

- Private athlete accounts, persistent profiles and explicit journal saving.
- Saved footage and manual coaching reports with integrity receipts and separate correction feedback.
- Practice tracking, evidence-linked reassessment, coverage dashboards and a rules-based personalized practice organizer.
- Athlete-authored tactical systems with an interactive decision explorer.
- Private opponent/style research notes and revocable coach review/comment access.
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

Application tests cover account isolation, password recovery/session revocation, CSRF, report integrity, coach grants/revocation, reassessment constraints, deletion and production refusal to use ephemeral training storage. CI also exercises PostgreSQL 18. Browser/camera workflows remain unverified under the user's existing preference; source and server checks do not establish browser compatibility.

Real athlete footage quality evaluation still needs permissioned footage and qualified reviewers. Whole-round automated analysis, continuous real-time computer vision, automated opponent scouting, a professionally validated tactics library, advanced motion/pose measurements and organizational administration are not part of this release. The current tactical builder and research journal are functioning foundations for those later capabilities.
