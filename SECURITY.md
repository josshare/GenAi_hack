### Security Policy

#### Supported Versions
- Main branch is supported for security updates.

#### Reporting a Vulnerability
- Please create a private security advisory in GitHub (Security > Advisories) with details and reproduction steps.
- If advisories are not available, contact the maintainers privately (replace with your contact).

#### Handling Secrets
- Do not commit real secrets. Use environment variables and AWS Secrets Manager/SSM Parameter Store.
- Use `config/config.example.yaml` as a template and keep real configs (e.g., `config/config.yaml`) out of Git.
- Populate `.env` locally based on `.env.example`; never commit `.env`.

#### Secret Rotation and Least Privilege
- Rotate credentials at least every 90 days.
- Use IAM roles with least privilege and short session durations.

#### Encryption
- Encrypt data at rest (KMS) and in transit (TLS).

#### CI/CD and Scanning Recommendations
- Enable GitHub Dependabot alerts and updates.
- Enable GitHub secret scanning and push protection.
- Consider `bandit`, `pip-audit` and `flake8` in CI.

#### Configuration Management
- Use `CONFIG_PATH` to point to non-committed config files.
- Validate configs before deploy; avoid hardcoded ARNs or account IDs in code.

#### Incident Response
- Log security-relevant events and keep audit trails.
- Provide a security contact and response SLA in this file once available.


