#!/usr/bin/env bash
# Read-only release candidate preflight. Does not fetch, check out, build, or deploy.
# Run with: ROOT=/opt/core8 RELEASE_SHA=<full-reviewed-sha> bash deploy/release-preflight.sh
set -euo pipefail

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
[[ -n "${RELEASE_SHA:-}" ]] || die "RELEASE_SHA (full 40-char Git SHA) is required"
[[ "$RELEASE_SHA" =~ ^[a-fA-F0-9]{40}$ ]] || die "RELEASE_SHA must be a full 40-character hexadecimal SHA"
ROOT="${ROOT:-/opt/core8}"
[[ -d "$ROOT/.git" ]] || die "ROOT is not an existing Git checkout: $ROOT"
command -v git >/dev/null || die "git is required"

# Deliberately offline: no git fetch, pull, checkout, file edits, container operations,
# firewall changes, env access or printing of secrets.
actual="$(git -C "$ROOT" rev-parse --verify "HEAD^{commit}")" || die "HEAD is invalid"
release="$(git -C "$ROOT" rev-parse --verify "$RELEASE_SHA^{commit}" 2>/dev/null)" || die "reviewed commit not available locally; fetch it manually before preflight"
[[ "$release" == "$RELEASE_SHA" ]] || die "candidate does not resolve exactly to RELEASE_SHA"
main="$(git -C "$ROOT" rev-parse --verify "refs/remotes/origin/main^{commit}" 2>/dev/null)" || die "origin/main missing; fetch it manually before preflight"
git -C "$ROOT" merge-base --is-ancestor "$RELEASE_SHA" "$main" || die "release candidate is not reachable from origin/main"
[[ -z "$(git -C "$ROOT" status --porcelain --untracked-files=no)" ]] || die "tracked working-tree changes exist; refuse release"
printf 'PRECHECK_ONLY=PASS\nROOT=%s\nCURRENT_SHA=%s\nCANDIDATE_SHA=%s\nORIGIN_MAIN_SHA=%s\n' "$ROOT" "$actual" "$release" "$main"
printf 'No deployment performed. Independent owner approval, backup, rollback and deploy checks are still required.\n'
