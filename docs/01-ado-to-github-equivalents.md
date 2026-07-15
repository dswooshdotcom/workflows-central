# ADO → GitHub Equivalents

A direct translation table for someone who knows ADO deeply. Every concept maps; the vocabulary differs.

---

## Pipelines & Workflows

| Azure DevOps | GitHub Actions | Notes |
|---|---|---|
| `azure-pipelines.yml` | `.github/workflows/*.yml` | GitHub allows multiple workflow files per repo; each is independent |
| Pipeline | Workflow | |
| Stage | Job (roughly) | GitHub Jobs are parallel by default; use `needs:` for sequencing |
| Job | Job | |
| Step | Step | Identical concept |
| Task (e.g. `UsePythonVersion@0`) | Action (e.g. `actions/setup-python@v5`) | GitHub calls them "Actions"; published to marketplace.github.com |
| `pool: vmImage: ubuntu-latest` | `runs-on: ubuntu-latest` | GitHub-hosted runners: ubuntu, windows, macos |
| `pool: name: MyAgentPool` | `runs-on: [self-hosted, my-label]` | Self-hosted runners use labels instead of pool names |
| Agent pool | Runner group | Org-level grouping of self-hosted runners |
| Variable group | Repository/org/environment secrets | Secrets are encrypted; no plain "variable groups" but env vars work |
| `$(myVar)` | `${{ vars.MY_VAR }}` or `${{ secrets.MY_SECRET }}` | Separate namespaces for vars vs secrets |
| `condition: succeeded()` | `if: success()` | GitHub uses JS-like expressions |
| `dependsOn:` | `needs:` | |
| Artifact (pipeline artifact) | Artifact (`actions/upload-artifact`) | Ephemeral — expires after N days; use Releases for durable storage |
| Release artifact | GitHub Release asset | **This is the durable artifact store in this system** |
| `$(Build.BuildId)` | `${{ github.run_id }}` | |
| `$(Build.SourceVersion)` | `${{ github.sha }}` | |
| `$(Build.Repository.Name)` | `${{ github.repository }}` | Returns `owner/repo` |
| `$(System.PullRequest.PullRequestNumber)` | `${{ github.event.pull_request.number }}` | |
| `$(Build.Reason)` | `${{ github.event_name }}` | e.g. `push`, `pull_request`, `workflow_dispatch` |

---

## Templates & Reuse

| Azure DevOps | GitHub Actions | Notes |
|---|---|---|
| YAML template (`extends:`) | Reusable workflow (`workflow_call`) | GitHub's version; called via `uses: org/repo/.github/workflows/foo.yml@ref` |
| Template parameters | Workflow inputs (`inputs:`) | Typed: `string`, `boolean`, `number`, `choice` |
| `secrets: inherit` | `secrets: inherit` | Identical syntax — passes all caller secrets to called workflow |
| Variable template | Not a native concept | Use composite actions or reusable workflows for shared logic |
| Task group | Composite action | Defined in `action.yml`; bundles steps into a reusable unit |
| `extends: template` (mandatory template) | Required workflow (org-level) | **Org admins can mandate that all repos run a specific workflow** — this is how you enforce the `build-artifact` standard at 500 repos |

---

## Environments & Approvals

| Azure DevOps | GitHub Actions | Notes |
|---|---|---|
| Environment | Environment | Same name; lives in repo Settings → Environments |
| Deployment gate | Environment protection rule | Supports required reviewers, wait timers, deployment branches |
| Pre-deployment approval | Required reviewers | Up to 6 people/teams; any one of them can approve |
| Post-deployment gate | Not native | Use a subsequent job with `if: success()` and a status check |
| Stage approval | Environment required reviewers | Gate on the job that targets the environment |
| Deployment group | Self-hosted runner group scoped to environment | Scope runners to specific environments so prod runners can't run dev jobs |

**Important:** In this POC, GitHub Environments are configured in `config-repo` → Settings → Environments → `prod` → Required reviewers. This replaces ADO's "pre-deployment approval" for the deploy workflow.

---

## Repositories & Branches

| Azure DevOps | GitHub Actions | Notes |
|---|---|---|
| Azure Repos | GitHub repos | Same concept |
| Branch policy | Branch protection rule | Settings → Branches → Add rule |
| Required build (policy) | Required status check | Add the workflow job name as a required check on the branch rule |
| Pull request | Pull request | Identical concept |
| "Allowed mergers" policy | CODEOWNERS + required review | `.github/CODEOWNERS` assigns reviewers by path |
| PR template | `.github/pull_request_template.md` | Automatically pre-fills PR body |
| Work item linking | Issue linking | Reference `#123` in commit message → GitHub auto-links to issue |
| Service connection | OIDC federated credential | **No stored secrets** — see [04-azure-oidc.md](04-azure-oidc.md) |

---

## Secrets & Variables

| Azure DevOps | GitHub Actions | Scope |
|---|---|---|
| Pipeline variable (secret) | Repository secret | One repo |
| Variable group (Key Vault linked) | Environment secret | One environment within one repo |
| Organization variable group | Organization secret | All repos in the org |
| Key Vault secret | Still Key Vault — accessed via OIDC + `azure/keyvault-secrets@v1` | Same vault, different access method |

**Hierarchy:** Organization secrets → Repository secrets → Environment secrets. Environment secrets override repo secrets of the same name when a job targets that environment.

---

## Triggers

| Azure DevOps trigger | GitHub Actions trigger | Notes |
|---|---|---|
| `trigger: branches: [main]` | `on: push: branches: [main]` | |
| `pr: branches: [main]` | `on: pull_request: branches: [main]` | |
| `schedules:` | `on: schedule: cron: '...'` | Standard cron syntax |
| `resources: pipelines:` (pipeline trigger) | `workflow_run:` | Trigger workflow B when workflow A completes |
| Manual run | `workflow_dispatch:` | Adds a "Run workflow" button in the Actions UI; supports inputs |
| `resources: repositories:` (repo trigger) | `on: push: paths:` | Filter by file paths within the same repo |
| Webhook | `repository_dispatch:` | External system POSTs to GitHub API → triggers workflow |

---

## Agent / Runner Types

| Azure DevOps | GitHub Actions | Notes |
|---|---|---|
| Microsoft-hosted agent (ubuntu-22.04) | `runs-on: ubuntu-22.04` | GitHub-hosted |
| Microsoft-hosted agent (windows-latest) | `runs-on: windows-latest` | GitHub-hosted |
| Self-hosted agent | Self-hosted runner | Must register with the repo/org; runs `./run.sh` or `./run.cmd` |
| Agent capability | Runner label | Label runners to target specific hardware/OS/env |
| Agent demand | `runs-on: [self-hosted, windows, gpu]` | Match multiple labels |
| Scale set agents (VMSS) | Larger runners / Actions Runner Controller (ARC) | ARC is the Kubernetes-native autoscaling runner controller |

For this POC's on-prem Windows deployment, the runner is self-hosted, Windows, and labelled by environment (`dev`, `staging`, `prod`).

---

## Access Control & Security

| Azure DevOps | GitHub Actions | Notes |
|---|---|---|
| Service connection (SP + client secret) | OIDC federated credential | Preferred — no stored secret; see [04-azure-oidc.md](04-azure-oidc.md) |
| Service connection (SP + cert) | OIDC federated credential | Same — OIDC replaces both SP auth methods |
| PAT | PAT | Both exist; avoid for automation |
| Azure AD group → ADO permission | GitHub team → repo permission | Map AD groups to GH teams via SCIM if using Entra ID SSO |
| Project-level permissions | Organization + repository permissions | GitHub has org-level roles (member, owner) and repo-level roles (read/triage/write/maintain/admin) |
| Audit log | Audit log (org Settings → Logs) | GitHub audit log streams to Splunk/SIEM via audit log streaming |
| Pipeline permissions (allow repo access) | `permissions:` block in workflow | Explicitly declare what `GITHUB_TOKEN` can do — principle of least privilege |

**Workflow permissions example** (equivalent to limiting a pipeline's service connection scope):
```yaml
permissions:
  contents: write      # needed to create releases
  pull-requests: write # needed to open PRs
  id-token: write      # needed for OIDC (Azure login)
```

---

## Artifacts & Releases

| Azure DevOps | GitHub Actions | Lifetime |
|---|---|---|
| Pipeline artifact (`PublishPipelineArtifact`) | `actions/upload-artifact` | Ephemeral — 90 days default |
| Universal Package (ADO Artifacts feed) | GitHub Packages (registry) | Persistent; versioned |
| **Release artifact (this system)** | **GitHub Release + asset** | **Persistent; tied to a git tag; downloadable with `gh release download`** |
| ADO Release pipeline drop | GitHub Release asset | Same concept — durable, versioned binary attached to a tag |

In this POC, **GitHub Releases are the durable artifact store**. Every successful build creates a Release with a timestamped tag. The config-repo references that tag. `gh release download` in the deploy workflow pulls the exact binary that was released.

---

## Notifications & Monitoring

| Azure DevOps | GitHub Actions | Notes |
|---|---|---|
| Build badge | `![Status](https://github.com/org/repo/actions/workflows/ci.yml/badge.svg)` | Embed in README |
| Email notification | Actions → Notification settings | Per-user preference for failed/passed runs |
| Service hook (Teams/Slack) | GitHub App for Teams/Slack | Install from Marketplace |
| Deployment event | `gh api .../deployments` | Records environment deployments; visible on repo home page |
| Release pipeline dashboard | Environments tab in GitHub repo | Shows current deployed version per environment |

---

## References

- [GitHub Actions documentation](https://docs.github.com/en/actions)
- [Reusable workflows deep dive](https://docs.github.com/en/actions/sharing-automations/reusing-workflows)
- [GitHub Environments](https://docs.github.com/en/actions/managing-workflow-runs-and-deployments/managing-deployments/managing-environments-for-deployment)
- [Required workflows (org-level enforcement)](https://docs.github.com/en/actions/managing-workflow-runs-and-deployments/managing-workflow-runs/required-workflows)
- [GITHUB_TOKEN permissions](https://docs.github.com/en/actions/security-for-github-actions/security-guides/automatic-token-authentication)
- [Actions Runner Controller (ARC)](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners-with-actions-runner-controller/about-actions-runner-controller)
