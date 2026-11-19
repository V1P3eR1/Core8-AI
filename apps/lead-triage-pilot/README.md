# Core8-AI lead-triage pilot (standalone, local)

A single-user tool for running a supervised pilot on real inbound inquiries.
You paste an inquiry in; it classifies it and drafts a reply; you edit, approve
or reject; you send the reply yourself. Every step lands in a tamper-evident
local log, and the tool turns that log into a redacted evidence report.

**Status: READY FOR REVIEW.** Not merged, not deployed, never run on real
inquiries. The live-model path has only been tested against a stub.

It is deliberately separate from `apps/core8-platform/`: single tenant, no
accounts, no database, no dependency on platform code. Platform issues #7 and
#11 neither block it nor are addressed by it, and nothing here is evidence that
the platform is ready.

## What it can and cannot do

- **Cannot send anything.** There is no email, WhatsApp, CRM or calendar code.
  "Sent" is a button you press after sending the reply yourself.
- **Cannot approve anything.** One human decision per inquiry: approve (the
  server records whether you edited the draft) or reject with a reason.
- **Keeps data on this computer.** One file, `events.jsonl`, in
  `~/.core8-lead-pilot/` by default. The tool refuses to start if the data
  folder is inside a git repository, so inquiries cannot be committed by mistake.
- **Binds to 127.0.0.1** and rejects requests with a foreign Host or Origin.

## Run it

Node 20 or newer. No install step, no dependencies.

```
cd apps/lead-triage-pilot
node server.cjs                 # http://127.0.0.1:4180/
```

### Engines

| Engine | Network | What drafts the reply |
|---|---|---|
| `rules` (default) | none | Keyword rules and fixed Hebrew/English templates with a `[Fill in: …]` placeholder you must complete |
| `anthropic` | one HTTPS call per draft to `api.anthropic.com` | A Claude model, told to classify and draft only, never to quote prices, terms or promises |

To use the live model, set these in your own shell — never in a file in this
repository:

```
CORE8_PILOT_ENGINE=anthropic ANTHROPIC_API_KEY=<your key> node server.cjs
```

`CORE8_PILOT_MODEL` overrides the model id (default `claude-sonnet-5-5`).
In this mode **the inquiry text is sent to the model API**. The label, channel
and your decisions are not. If the call fails or returns something malformed,
the offline rules draft is used and the reason is logged.

Drafts that mention a price, a percentage, a promise or a link are flagged for
the reviewer. Flags warn; they do not block.

## Website-form leads

The landing page's form handler (`apps/landing/server/lead.php`, PR #32) e-mails
each submission to the business mailbox as a `CORE8 LEAD v1` message: a fixed
subject tag `[CORE8-LEAD]` and one signed, machine-readable block.

Today that e-mail is **pasted** into "Add a website-form e-mail". The tool
checks the signature, refuses submissions without consent, ignores duplicates,
and creates the lead with its contact details and consent record.

```
CORE8_LEAD_SECRET=<same secret as lead-config.php> node server.cjs
```

With the secret set, unsigned or altered e-mails are refused. Without it they
are accepted and marked "unsigned".

**Not built yet: reading the mailbox automatically.** That needs a decision on
how the tool is given access to the mailbox and where it runs; until then a
person copies the e-mail in.

For leads where a conversation is the likely next step, the tool suggests three
meeting times from fixed working hours (Sun–Thu). **It cannot see any
calendar**; the times are unchecked suggestions.

The **Leads table** lists every lead and exports a CSV. That CSV holds names and
contact details and is personal data.

## The audit log

Each line of `events.jsonl` is one event (`lead_added`, `triage_completed`,
`decision_recorded`, `marked_sent`) carrying the SHA-256 of the previous event.
Editing, deleting or reordering any line breaks the chain: the UI shows it and
the server refuses to append to a broken log. This detects tampering after the
fact; it does not prevent someone with access to the computer from deleting the
whole file. Back the folder up.

**Download evidence report** produces a JSON file with metrics, the chain
verification result and one hash per event. It contains no inquiry text, drafts,
labels, names or reasons, so it can be shown to third parties.

## Metrics, and what they do and do not mean

| Metric | Meaning | Caveat |
|---|---|---|
| Approved as drafted | Share of decisions where the draft went out unchanged | With the `rules` engine this is always 0: templates must be filled in |
| Approved after edit / Rejected | Share needing your changes, or unusable | The honest quality signal for the draft engine |
| Median review time | Draft ready → your decision | Includes time the inquiry sat unopened |
| Median received → sent | Time you entered as "received" → you pressed "I sent it myself" | Only as accurate as those two human inputs |

There is no built-in baseline. To claim an improvement, record how long replies
took before the pilot, over a comparable period, and keep that record.

## Running it on a server, and reading the mailbox

Local use needs none of this. For a server:

- `CORE8_PILOT_PUBLIC_HOST` + `CORE8_PILOT_PASSWORD_HASH` turn on sign-in
  (`public/login.html`). The process refuses to start on a public address
  without a password. Make the hash with `node tools/hash-password.cjs`, or use
  `CORE8_PILOT_PASSWORD_HASH_FILE` and `node tools/set-password.cjs`: the tool
  then starts locked until the owner sets a password on the server.
- `CORE8_PILOT_IMAP_USER` + `CORE8_PILOT_IMAP_PASS` (an app password) turn on a
  read-only mailbox check (`lib/mailbox.cjs`): `EXAMINE`, a server-side search
  for `[CORE8-LEAD]` in the subject, and `BODY.PEEK`. It cannot send, move,
  flag or delete mail, and other messages are never downloaded.
- `deploy/` holds a Dockerfile, a compose file with no published port, a Caddy
  site block and a step-by-step guide. **Prepared, not deployed; the image has
  not been built** (no Docker daemon was available where this was written).

## Tests

```
npm test               # 47 tests: log integrity, triage engines, metrics, HTTP API, form-e-mail intake, sign-in, mailbox reader
npm run test:browser   # 13 + 5 browser checks; needs Playwright and Chrome
```

Last recorded run (2026-11-19, Node 22.23.5, Playwright 1.63.0, Chrome 153,
Linux): 47 of 47, 13 of 13 and 5 of 5 passed. One test parses a message produced by the
real PHP handler and verifies its signature. The mailbox reader is tested against
a local fake IMAP server that records every command, to show only read-only
commands are sent. Screenshots from that run, using made-up
inquiries, are in `docs/evidence/lead-triage-pilot/`.

Not tested: a real mailbox (Gmail IMAP over TLS) or real e-mail delivery, the
Docker image, a real reverse proxy, the real Anthropic API (no key was used; the adapter is exercised
with a stub), Windows, macOS, Firefox, Safari, screen readers.

## Before using it on real inquiries

1. Inquiries contain personal data. Decide whether sending their text to a
   model API is acceptable for your privacy notice and for the people writing in.
2. Keep the data folder out of cloud-synced and shared locations unless that is
   intended.
3. Read every draft. The model is instructed to treat inquiry text as data, but
   the human review is the control, not the instruction.
