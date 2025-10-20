### GitHub Actions AWS credentials helper

Scripts to create an IAM user and generate AWS access keys for use in GitHub Actions.

Prereqs:
- AWS CLI configured with sufficient permissions
- `jq` installed

Create user and keys (default user `github-actions-ci` with PowerUserAccess):

```bash
bash scripts/gha-credentials/create_iam_user_and_keys.sh
```

Custom options:

```bash
IAM_USER_NAME=my-ci-user \
POLICY_ARN=arn:aws:iam::aws:policy/AdministratorAccess \
AWS_PROFILE=default \
AWS_REGION=us-east-1 \
OUTPUT_DIR=scripts/gha-credentials/generated \
bash scripts/gha-credentials/create_iam_user_and_keys.sh
```

Output files:
- `scripts/gha-credentials/generated/access_keys.json`
- `scripts/gha-credentials/generated/github-actions-secrets.env`

Format for GitHub secrets (prints key=value or uses gh CLI if REPO is set):

```bash
bash scripts/gha-credentials/format_for_github.sh

REPO=OWNER/REPO bash scripts/gha-credentials/format_for_github.sh
```

Security note: Access keys are sensitive. Files are gitignored; rotate keys if leaked.


