# workflows-central

Central reusable workflows for the GitOps non-containerized artifact system. All 500 app repos call workflows defined here — changing a workflow here changes behavior for every app without touching individual repos.

## Repo map

```
.github/
  workflows/
    build-artifact.yml     ← reusable workflow: build → GitHub Release → config-repo PR
  scripts/
    open_config_pr.py      ← Python: opens the config-repo promotion PR after a release

docs/
  00-architecture.md              ← system overview, flow diagram, scaling strategy
  01-ado-to-github-equivalents.md ← direct ADO → GitHub translation table
  02-setup-guide.md               ← step-by-step setup for this POC
  03-secrets-auth.md              ← PAT vs GitHub App, secret scopes
  04-azure-oidc.md                ← 2027 Azure migration: OIDC federated credentials
  05-versioning.md                ← @main vs @v1 vs SHA pinning, required workflows
  06-security.md                  ← self-hosted runner hardening, branch protection, CODEOWNERS
  07-adding-a-new-app.md          ← developer onboarding playbook
  08-self-hosted-runners.md       ← Windows runner install, labels, groups, maintenance
  09-current-state.md             ← what's deployed, what's wired, what's left to do
```

## Quick reference

### Calling this workflow from an app repo

```yaml
# app-repo/.github/workflows/ci.yml
jobs:
  build-and-promote:
    uses: dswooshdotcom/workflows-central/.github/workflows/build-artifact.yml@main
    with:
      app-name: my-app            # must match apps/<app-name>/ in config-repo
      build-command: |            # produces artifact.zip in workspace root
        zip -r artifact.zip src/
      config-repo: dswooshdotcom/config-repo
    secrets:
      CONFIG_REPO_TOKEN: ${{ secrets.CONFIG_REPO_TOKEN }}
```

### Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `app-name` | Yes | — | Logical app name; must match `apps/<app-name>/` in config-repo |
| `build-command` | No | `zip -r artifact.zip src/` | Shell command that produces the artifact |
| `artifact-path` | No | `artifact.zip` | Path of the built file to attach to the GitHub Release |
| `config-repo` | No | `dswooshdotcom/config-repo` | `owner/repo` of the config repo |

### Secrets

| Secret | Required | Description |
|--------|----------|-------------|
| `CONFIG_REPO_TOKEN` | Yes | PAT or GitHub App token with `contents:write` and `pull-requests:write` on config-repo |

## Related repos

- [`dswooshdotcom/app-sample`](https://github.com/dswooshdotcom/app-sample) — example caller repo
- [`dswooshdotcom/config-repo`](https://github.com/dswooshdotcom/config-repo) — environment state and deploy trigger

## Start here

→ [Current state — what's live, what's wired, what's left](docs/09-current-state.md)  
→ [Architecture overview](docs/00-architecture.md)  
→ [Setup guide](docs/02-setup-guide.md)  
→ [ADO → GitHub equivalents](docs/01-ado-to-github-equivalents.md)
