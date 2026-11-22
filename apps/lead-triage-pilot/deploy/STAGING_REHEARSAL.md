# Core8-AI lead intake: protected staging rehearsal

Status: **review-only plan**. This file does not provision, authorize or deploy anything.
Related: [PR #31](https://github.com/V1P3eR1/Core8-AI/pull/31), [PR #32](https://github.com/V1P3eR1/Core8-AI/pull/32), [#49](https://github.com/V1P3eR1/Core8-AI/issues/49), [release PR #55](https://github.com/V1P3eR1/Core8-AI/pull/55).

## What is already independently proven in CI

- `lead-triage-contract.yml` runs Node tests, PHP producer → Node consumer on pinned draft heads, and real local Chromium browser flows.
- The PHP handler runs **spool mode**, never `mail()`. The signed message is verified, deduplicated and turns into `needs_review` without sending anything.
- An offline synthetic event-log snapshot can be restored with the exact same audit head hash. A tampered synthetic backup is rejected.
- Public-mode mailbox intake requires `CORE8_LEAD_SECRET`; public cleartext IMAP configuration is rejected. Default IMAP TLS uses Node certificate verification.

The above is **NOT** evidence of a real inbox, hosted staging, production backup or DNS readiness.

## Staging design — no production data

1. Owner approves a **separate staging environment** and a reviewed **immutable SHA** for each proposed component. Do not use floating `main` or a PR branch name as a deployment source.
2. Provision staging on a separate namespace/host/database/volume isolated from production. Do not copy production `.env`, account tokens, DB, mailbox or private manuscripts.
3. Restrict access to nominated testers (authentication and preferably network allowlist); set `CORE8_PILOT_ENGINE=rules`. Disable all scheduled outbound messages and live publishing; the lead agent must retain **no send capability**.
4. Set a staging-only `CORE8_LEAD_SECRET` in a private secret manager, never in GitHub or CI logs. Test operator identity and password hash using a staging-only account.
5. Configure an explicitly authorized **test mailbox** with independent credentials and TLS certificate validation. To test real delivery, send one synthetic lead using an approved test sender **only after** operator authorization; record only delivery/receipt status and a random synthetic submission ID in evidence.
6. Confirm behavior: valid signed form → read-only IMAP (`EXAMINE`, `UID SEARCH`, `BODY.PEEK`) → one `needs_review` lead, repeat polling and UIDVALIDITY reset yield no duplicates, forged/missing consent yield rejection. Test the human draft/approve flow without transmitting replies.
7. Rehearse encrypted backup of the entire staging volume, including `events.jsonl`, `mailbox-state.json` and password-hash state. Restore to a **new disposable** volume while the original is left unchanged; inspect record count, audit head, duplicate submission ID handling and access permissions. Verify that recovery keys can be obtained by an authorized operator. Securely delete only disposable synthetic evidence under an approved retention schedule.
8. Run a basic outage drill: stop the **staging** process, verify restored instance boots from the approved immutable code SHA, and demonstrate rollback using an earlier staging-only snapshot. Capture durations and a redacted go/no-go report.
9. Review legal notice/consent versions, retention/deletion and data-subject processes before collecting anything real.

## Gates and evidence record

| Gate | Evidence required | State |
|---|---|---|
| Offline Node, signed PHP/Node, browser smoke | GitHub Actions links on exact reviewed SHA | VERIFIED IN CI |
| Staging dedicated environment, no production data | Host/volume inventory with secret values redacted | NOT VERIFIED |
| Approved staging domain/access controls | Authentication, network policy test | NOT VERIFIED |
| Real test-mail delivery and TLS IMAP | Provider message ID (redacted), read-only IMAP transcript | NOT VERIFIED |
| Backup encryption and independent restore | Restore hash, audit verification, rollback evidence | NOT VERIFIED |
| Privacy/consent/retention | Reviewed versions and owner approval | NOT VERIFIED |
| Production release | Owner's explicit merge/deploy authorization | NOT AUTHORIZED |

## Safety boundary

This runbook is **not an instruction to run commands against the live VPS**. No live credentials are needed for the existing offline tests. Avoid public CI artifacts containing contact info or screenshots with real personal data. Never post staging secrets in issue comments. Owner approval is required separately for credentials, deployment, live mail traffic, data migration, DNS, paid AI usage and customer activation.
