# Core8-AI reproducible release — preflight contract (draft)

**Status:** proposal / read-only proof, not an authorized deployment pathway. Tracks [#48](https://github.com/V1P3eR1/Core8-AI/issues/48). This PR does not modify `install.sh`, VPS, DNS or production.

## Observed unsafe legacy behavior
`apps/core8-platform/deploy/install.sh` on `main` defaults to a mutable `feature/social-manager` branch, updates a checkout via `git pull` and immediately runs `docker compose up -d --build`. **Do not use this installer unattended.** The proposed read-only preflight is a first gate, not a substitute for a release controller.

## Use of the new preflight
On a disposable local checkout (not on the live VPS), fetch verified `origin/main` separately, then:

```bash
ROOT=/path/to/safe/local/clone RELEASE_SHA=0123456789abcdef0123456789abcdef01234567 \
  bash apps/core8-platform/deploy/release-preflight.sh
```

Replace the illustrative SHA with the **real reviewed full 40-character commit SHA**. The script must reject:
- Absent, shortened or malformed SHA.
- Missing checkout or missing local candidate commit.
- Candidate not an ancestor of local `origin/main`.
- Modified tracked checkout files **or untracked files** that could change an unreviewed Docker build context. Git-ignored runtime configuration (for example `.env.production`) is neither read nor printed.

It prints candidate/current/main SHAs and reports **PRECHECK_ONLY**, without checking out a branch, fetching, deploying, opening ports, reading environment values or altering files. The script uses locally cached remote refs, which may be stale: validating the authentic remote fetch and signed release provenance belongs to a separate gate.

## Required before any production apply
1. Decide authoritative release SHA after PR reviews and CI, then confirm SHA on a verified GitHub remote.
2. Authenticate the human operator out-of-band and separately authorize production scope.
3. Validate compose/Caddy configuration and deployment manifest without printing secrets.
4. Record current VPS SHA from the *actual* machine, not from GitHub, and compare against target.
5. Prove encrypted, restorable DB/media backup and schema-migration rollback on a staging clone.
6. Only then build a deployment script with non-interactive default denial and explicit approval (separate follow-up PR). Preserve existing services including Caddy routing #44.

## Out of scope
No automatic deployment, no branches merged, no credentials touched, no confirmation that this script is installed on the VPS. Existing PR #41 may be stale/conflicted; do not merge it just to satisfy this proposal.
