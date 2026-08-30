# EKS GitOps Setup

This repository is the workload and GitOps source for ChangeGuard AI Release Ops.

## Safety model

1. ChangeGuard uses LangChain with `gpt-4o-mini` to interpret a developer request and collect specialist opinions.
2. Deterministic policy requires a protected branch, semantic version, target environments, and a change-request issue for production.
3. Execution revalidates that the issue is open and has the `change-approved` label.
4. GitHub Actions repeats that validation and pauses the production job for GitHub Environment approval.
5. Argo CD reconciles versioned Helm values into `dev`, `qa`, and `prod` namespaces.
6. Argo Rollouts shifts traffic-equivalent replica weight through 20% and 50% canary stages.
7. Prometheus verifies pod-readiness ratios at each stage; failed analysis aborts promotion and preserves the stable revision.

The workflow never receives long-lived AWS keys. GitHub exchanges its OIDC token for the scoped ECR publishing role.

Argo CD owns desired-state synchronization. Argo Rollouts owns progressive replacement and rollback. Prometheus supplies objective analysis measurements; none of these decisions are delegated to the language model.

## Prerequisites

- AWS CLI authenticated to the target account
- Terraform, Helm, kubectl, Argo CD CLI, and GitHub CLI
- GitHub CLI authenticated with `gh auth login`
- OpenAI key configured only in the ChangeGuard backend

## Provision

```powershell
.\scripts\configure-github.ps1
.\scripts\bootstrap-eks.ps1
```

After Terraform completes:

1. Commit the ECR URL written into `gitops/environments/*/values.yaml`.
2. Set repository variable `AWS_RELEASE_ROLE_ARN` to the Terraform output.
3. Set `ARGOCD_SERVER` and `ARGOCD_AUTH_TOKEN` as GitHub environment secrets for dev, qa, and production.
4. Add required reviewers to the GitHub `production` environment.
5. Push the repository to GitHub.
6. Create a GitHub issue for each production change and apply `change-approved` only after review.

## Cost

The default creates two `t3.large` worker nodes and one NAT gateway in `us-east-1`. Run `terraform destroy` from `infra/terraform` when the lab is not needed.