#!/usr/bin/env bash
set -euo pipefail

# Helper: Format existing generated keys into GitHub CLI secret set commands.

OUTPUT_DIR=${OUTPUT_DIR:-"$(dirname "$0")/generated"}
REPO=${REPO:-""} # Format: OWNER/REPO; leave empty to just echo key=value lines

ACCESS_FILE="$OUTPUT_DIR/access_keys.json"

if [[ ! -f "$ACCESS_FILE" ]]; then
  echo "No access_keys.json found at $ACCESS_FILE. Run create_iam_user_and_keys.sh first." >&2
  exit 1
fi

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || return 1
}

AWS_ACCESS_KEY_ID=$(jq -r '.AccessKey.AccessKeyId' "$ACCESS_FILE")
AWS_SECRET_ACCESS_KEY=$(jq -r '.AccessKey.SecretAccessKey' "$ACCESS_FILE")

if [[ -z "$REPO" ]]; then
  echo "AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID"
  echo "AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY"
  exit 0
fi

if require_cmd gh; then
  gh secret set AWS_ACCESS_KEY_ID --repo "$REPO" --body "$AWS_ACCESS_KEY_ID"
  gh secret set AWS_SECRET_ACCESS_KEY --repo "$REPO" --body "$AWS_SECRET_ACCESS_KEY"
else
  echo "gh CLI not found. Install GitHub CLI or export REPO='' to print key=value."
  exit 1
fi


