#!/usr/bin/env bash
# Purpose: Ensure required GitHub Actions AWS secrets/variables exist.
# - Secrets: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN (optional)
# - Variable: AWS_REGION
#
# Requirements:
# - gh CLI authenticated with repo write perms: https://cli.github.com/
#
# Usage examples:
#   # Using env vars and repo from current directory
#   AWS_ACCESS_KEY_ID=AKIA... \
#   AWS_SECRET_ACCESS_KEY=xxxx \
#   AWS_SESSION_TOKEN=yyyy \  # optional if using long‑lived keys
#   AWS_REGION=us-east-1 \
#   ./scripts/gha-credentials/set_github_aws_credentials.sh
#
#   # Target a specific repo
#   GITHUB_REPOSITORY=owner/repo AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_REGION=eu-west-1 \
#   ./scripts/gha-credentials/set_github_aws_credentials.sh
#
#   # Use an Actions Environment (e.g., prod)
#   ENVIRONMENT=prod AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_REGION=us-east-1 \
#   ./scripts/gha-credentials/set_github_aws_credentials.sh

set -euo pipefail

echo "[info] Ensuring GitHub Actions secrets/variables for AWS are present..."

# ---------- Config & helpers ----------
REPO="${GITHUB_REPOSITORY:-}"
ENVIRONMENT="${ENVIRONMENT:-}"

AWS_ACCESS_KEY_ID_VAL="${AWS_ACCESS_KEY_ID:-}"
AWS_SECRET_ACCESS_KEY_VAL="${AWS_SECRET_ACCESS_KEY:-}"
AWS_SESSION_TOKEN_VAL="${AWS_SESSION_TOKEN:-}"
AWS_REGION_VAL="${AWS_REGION:-}"

if ! command -v gh >/dev/null 2>&1; then
  echo "[error] gh CLI is required. Install from https://cli.github.com/" >&2
  exit 1
fi

# Determine repo if not provided
if [[ -z "$REPO" ]]; then
  if REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null); then
    export GITHUB_REPOSITORY="$REPO"
  else
    echo "[error] Could not detect repository. Set GITHUB_REPOSITORY=owner/repo" >&2
    exit 1
  fi
fi

REPO_ARG=( -R "$REPO" )

# Scope: repo-level or environment-level
SCOPE_SEC=()
SCOPE_VAR=()
if [[ -n "$ENVIRONMENT" ]]; then
  SCOPE_SEC=( --env "$ENVIRONMENT" )
  SCOPE_VAR=( --env "$ENVIRONMENT" )
  echo "[info] Targeting Environment secrets/variables: $ENVIRONMENT"
else
  echo "[info] Targeting Repository secrets/variables"
fi

list_secrets() {
  if [[ ${#SCOPE_SEC[@]} -eq 0 ]]; then
    gh secret list "${REPO_ARG[@]}" | awk '{print $1}' || true
  else
    gh secret list "${REPO_ARG[@]}" "${SCOPE_SEC[@]}" | awk '{print $1}' || true
  fi
}

list_variables() {
  if [[ ${#SCOPE_VAR[@]} -eq 0 ]]; then
    gh variable list "${REPO_ARG[@]}" | awk '{print $1}' || true
  else
    gh variable list "${REPO_ARG[@]}" "${SCOPE_VAR[@]}" | awk '{print $1}' || true
  fi
}

has_secret() {
  local name="$1"
  list_secrets | grep -qx "$name"
}

has_variable() {
  local name="$1"
  list_variables | grep -qx "$name"
}

set_secret_if_missing() {
  local name="$1"; shift
  local value="$1"; shift || true
  if [[ -z "$value" ]]; then
    echo "[warn] Skipping $name: value is empty (env var not provided)."
    return 0
  fi
  if has_secret "$name"; then
    echo "[ok] Secret $name already exists. Skipping."
  else
    echo "[set] Creating secret $name"
    # Use --body to avoid passing via stdin
    if [[ ${#SCOPE_SEC[@]} -eq 0 ]]; then
      gh secret set "$name" "${REPO_ARG[@]}" --body "$value"
    else
      gh secret set "$name" "${REPO_ARG[@]}" "${SCOPE_SEC[@]}" --body "$value"
    fi
  fi
}

set_variable_if_missing() {
  local name="$1"; shift
  local value="$1"; shift || true
  if [[ -z "$value" ]]; then
    echo "[warn] Skipping variable $name: value is empty (env var not provided)."
    return 0
  fi
  if has_variable "$name"; then
    echo "[ok] Variable $name already exists. Skipping."
  else
    echo "[set] Creating variable $name"
    if [[ ${#SCOPE_VAR[@]} -eq 0 ]]; then
      gh variable set "$name" "${REPO_ARG[@]}" --body "$value"
    else
      gh variable set "$name" "${REPO_ARG[@]}" "${SCOPE_VAR[@]}" --body "$value"
    fi
  fi
}

# ---------- Apply ----------
set_secret_if_missing AWS_ACCESS_KEY_ID "$AWS_ACCESS_KEY_ID_VAL"
set_secret_if_missing AWS_SECRET_ACCESS_KEY "$AWS_SECRET_ACCESS_KEY_VAL"
set_secret_if_missing AWS_SESSION_TOKEN "$AWS_SESSION_TOKEN_VAL"
set_variable_if_missing AWS_REGION "$AWS_REGION_VAL"

echo "[done] Completed ensuring AWS secrets/variables for $REPO${ENVIRONMENT:+ (env: $ENVIRONMENT)}."

