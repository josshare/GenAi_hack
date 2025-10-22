# GitHub Actions OIDC Setup for AWS

This guide provides instructions for configuring your AWS account to allow GitHub Actions to deploy resources using OpenID Connect (OIDC). This is the recommended secure method for authentication, as it does not require storing long-lived access keys in GitHub.

## Overview

The process involves three main steps:
1.  **Configure the IAM OIDC Identity Provider:** Set up a trust relationship between your AWS account and GitHub's OIDC provider.
2.  **Create an IAM Role for GitHub Actions:** Create a role with a trust policy that allows principals from your GitHub repository to assume it. Attach the necessary permissions policies to this role.
3.  **Add the Role ARN to GitHub Secrets:** Store the ARN of the newly created IAM role in a GitHub repository secret named `AWS_ROLE_TO_ASSUME`.

---

## Step 1: Configure the IAM OIDC Identity Provider

1.  Navigate to the **IAM** console in AWS.
2.  In the left sidebar, click on **Identity providers**.
3.  Click **Add provider**.
4.  For **Provider type**, select **OpenID Connect**.
5.  For **Provider URL**, enter `https://token.actions.githubusercontent.com`.
6.  Click **Get thumbprint** to verify the server certificate.
7.  For **Audience**, enter `sts.amazonaws.com`.
8.  Click **Add provider**.

You only need to do this once per AWS account. If the provider already exists, you can skip to the next step.

---

## Step 2: Create an IAM Role for GitHub Actions

Next, you will create a role that GitHub Actions can assume to gain permissions in your AWS account.

1.  In the IAM console, go to **Roles** and click **Create role**.
2.  For **Trusted entity type**, select **Custom trust policy**.
3.  In the policy editor, paste the following JSON. **Replace `OWNER/REPO` with your GitHub repository owner and name** (e.g., `josshare/GenAi_hack`).

    ```json
    {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Federated": "arn:aws:iam::ACCOUNT-ID-WITHOUT-HYPHENS:oidc-provider/token.actions.githubusercontent.com"
                },
                "Action": "sts:AssumeRoleWithWebIdentity",
                "Condition": {
                    "StringEquals": {
                        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
                    },
                    "StringLike": {
                        "token.actions.githubusercontent.com:sub": "repo:OWNER/REPO:*"
                    }
                }
            }
        ]
    }
    ```

    *   **Important:** You must replace `ACCOUNT-ID-WITHOUT-HYPHENS` with your actual 12-digit AWS Account ID. You can find this in the top right corner of the AWS Management Console.
    *   The `StringLike` condition `repo:OWNER/REPO:*` ensures that only workflows from your specified repository can assume this role.

4.  Click **Next**.
5.  On the **Add permissions** page, attach the policies that your deployment process needs. For this project, the following policies are required:
    *   `PowerUserAccess`: Provides broad permissions for creating and managing AWS resources. For a production environment, it is highly recommended to create a more restrictive, least-privilege policy with only the permissions your CloudFormation stack requires (e.g., IAM, S3, Lambda, CloudWatch).
6.  Click **Next**.
7.  For **Role name**, enter a descriptive name, such as `GitHubActions-ai-agent-deployment-role`.
8.  Review the settings and click **Create role**.
9.  Once the role is created, click on its name to view the details page and **copy the Role ARN**. It will look like `arn:aws:iam::123456789012:role/GitHubActions-ai-agent-deployment-role`.

---

## Step 3: Add the Role ARN to GitHub Secrets

The final step is to provide the Role ARN to your GitHub Actions workflow.

1.  Navigate to your repository on GitHub and go to **Settings** > **Secrets and variables** > **Actions**.
2.  Click **New repository secret**.
3.  For **Name**, enter `AWS_ROLE_TO_ASSUME`.
4.  For **Value**, paste the **Role ARN** you copied from the AWS console.
5.  Click **Add secret**.

Your workflow is now configured to securely authenticate with AWS. When the workflow runs, the `configure-aws-credentials` action will automatically use the OIDC token to assume the IAM Role and obtain temporary credentials.
