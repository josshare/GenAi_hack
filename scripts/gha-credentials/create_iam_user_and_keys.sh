#!/usr/bin/env bash
set -euo pipefail

# Creates/ensures an IAM user and generates programmatic access keys for GitHub Actions.
# Outputs keys to a local generated directory and prints values to paste into GitHub Secrets.

# Defaults (override via env or flags)
IAM_USER_NAME=${IAM_USER_NAME:-"github-actions-ci"}
POLICY_ARN=${POLICY_ARN:-"arn:aws:iam::aws:policy/PowerUserAccess"}
TAGS=${TAGS:-"project=GenAi_hack,owner=github-actions"}
OUTPUT_DIR=${OUTPUT_DIR:-"$(dirname "$0")/generated"}
AWS_PROFILE_FLAG=${AWS_PROFILE:+--profile "$AWS_PROFILE"}
AWS_REGION_FLAG=${AWS_REGION:+--region "$AWS_REGION"}

usage() {
  cat <<EOF
Usage: $(basename "$0") [--user NAME] [--policy ARN] [--tags k=v,k=v] [--output DIR]
Environment vars:
  IAM_USER_NAME       Default: github-actions-ci
  POLICY_ARN          Default: arn:aws:iam::aws:policy/PowerUserAccess
  TAGS                Comma-separated, e.g. key1=val1,key2=val2
  OUTPUT_DIR          Default: scripts/gha-credentials/generated
  AWS_PROFILE         Optional: AWS CLI profile
  AWS_REGION          Optional: AWS region for service calls

This script will:
  - Ensure IAM user exists
  - Attach policy to the user
  - Create a new access key pair
  - Save keys to: 
      $OUTPUT_DIR/access_keys.json
      $OUTPUT_DIR/github-actions-secrets.env
  - Print values to paste into GitHub Secrets
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --user)
      IAM_USER_NAME="$2"; shift 2 ;;
    --policy)
      POLICY_ARN="$2"; shift 2 ;;
    --tags)
      TAGS="$2"; shift 2 ;;
    --output)
      OUTPUT_DIR="$2"; shift 2 ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "Unknown argument: $1" >&2; usage; exit 1 ;;
  esac
done

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "Required command '$1' not found in PATH" >&2; exit 1; }
}

require_cmd aws
require_cmd jq
mkdir -p "$OUTPUT_DIR"

echo "[1/5] Checking IAM user: $IAM_USER_NAME"
set +e
aws iam get-user --user-name "$IAM_USER_NAME" $AWS_PROFILE_FLAG $AWS_REGION_FLAG >/dev/null 2>&1
USER_EXISTS=$?
set -e

if [[ $USER_EXISTS -ne 0 ]]; then
  echo "[2/5] Creating IAM user: $IAM_USER_NAME"
  TAG_ARGS=()
  IFS=',' read -r -a TAG_PAIRS <<< "$TAGS"
  for pair in "${TAG_PAIRS[@]}"; do
    key="${pair%%=*}"; val="${pair#*=}"
    [[ -n "$key" && -n "$val" ]] && TAG_ARGS+=(Key="$key",Value="$val")
  done

  if [[ ${#TAG_ARGS[@]} -gt 0 ]]; then
    aws iam create-user \
      --user-name "$IAM_USER_NAME" \
      --tags "${TAG_ARGS[@]}" \
      $AWS_PROFILE_FLAG $AWS_REGION_FLAG >/dev/null
  else
    aws iam create-user --user-name "$IAM_USER_NAME" $AWS_PROFILE_FLAG $AWS_REGION_FLAG >/dev/null
  fi
else
  echo "[2/5] IAM user already exists"
fi

echo "[3/5] Ensuring policy attachment: $POLICY_ARN"
set +e
aws iam list-attached-user-policies --user-name "$IAM_USER_NAME" $AWS_PROFILE_FLAG $AWS_REGION_FLAG \
  | grep -q "$POLICY_ARN"
ATTACHED=$?
set -e

if [[ $ATTACHED -ne 0 ]]; then
  aws iam attach-user-policy --user-name "$IAM_USER_NAME" --policy-arn "$POLICY_ARN" $AWS_PROFILE_FLAG $AWS_REGION_FLAG
  echo "  Attached policy"
else
  echo "  Policy already attached"
fi

echo "[4/5] Creating access keys"
ACCESS_KEYS_JSON=$(aws iam create-access-key --user-name "$IAM_USER_NAME" $AWS_PROFILE_FLAG $AWS_REGION_FLAG)
echo "$ACCESS_KEYS_JSON" | jq . > "$OUTPUT_DIR/access_keys.json"

AWS_ACCESS_KEY_ID=$(echo "$ACCESS_KEYS_JSON" | jq -r '.AccessKey.AccessKeyId')
AWS_SECRET_ACCESS_KEY=$(echo "$ACCESS_KEYS_JSON" | jq -r '.AccessKey.SecretAccessKey')

ENV_FILE="$OUTPUT_DIR/github-actions-secrets.env"
cat > "$ENV_FILE" <<ENV
AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY
ENV

chmod 600 "$ENV_FILE"

echo "[5/5] Done. Files generated in: $OUTPUT_DIR"
echo
echo "Paste these into GitHub Secrets for your repo (Settings > Secrets and variables > Actions > New repository secret):"
echo "  AWS_ACCESS_KEY_ID = $AWS_ACCESS_KEY_ID"
echo "  AWS_SECRET_ACCESS_KEY = $AWS_SECRET_ACCESS_KEY"
echo
echo "Optional: If you have GitHub CLI installed, you can set secrets like this (replace OWNER/REPO):"
echo "  gh secret set AWS_ACCESS_KEY_ID --repo OWNER/REPO --body '$AWS_ACCESS_KEY_ID'"
echo "  gh secret set AWS_SECRET_ACCESS_KEY --repo OWNER/REPO --body '$AWS_SECRET_ACCESS_KEY'"


