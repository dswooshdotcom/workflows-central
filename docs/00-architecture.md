# Architecture: GitOps for Non-Containerized Artifacts

## Overview

This system implements a **GitOps pull model** for deploying non-containerized apps (`.exe`, `.zip`, `.dll`, `.msi`, SQL scripts, batch DLLs) across on-premises environments. Instead of pushing deployments imperatively, environment state lives in a `config-repo` as YAML. Merging a change to that YAML is the deployment trigger.

The design mirrors what this org already does in Azure DevOps (ADO) but implemented natively in GitHub Actions, setting the foundation for the 2027 on-prem → Azure migration.

---

## Three-Repo Structure

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        GitHub Organization                               │
│                                                                          │
│  ┌──────────────────────┐    ┌──────────────────────┐                   │
│  │   app-sample         │    │   app-billing         │   ...500 repos    │
│  │   (any app repo)     │    │   (another app)       │                   │
│  │                      │    │                       │                   │
│  │  .github/            │    │  .github/             │                   │
│  │    workflows/        │    │    workflows/         │                   │
│  │      ci.yml  ────────┼────┼──────────────────────┼──────┐            │
│  └──────────────────────┘    └──────────────────────┘      │            │
│                                                             │ uses:      │
│  ┌──────────────────────────────────────────────────────────▼──────────┐ │
│  │   workflows-central                                                  │ │
│  │   (org-level reusable workflows)                                     │ │
│  │                                                                      │ │
│  │  .github/                                                            │ │
│  │    workflows/                                                        │ │
│  │      build-artifact.yml   ← ONE workflow, consumed by all 500 repos │ │
│  │    scripts/                                                          │ │
│  │      open_config_pr.py    ← opens PR on config-repo after build     │ │
│  └──────────────────────────────────────┬───────────────────────────────┘ │
│                                         │ opens PR                        │
│  ┌──────────────────────────────────────▼───────────────────────────────┐ │
│  │   config-repo                                                         │ │
│  │   (environment state — this IS the deployment)                       │ │
│  │                                                                       │ │
│  │  apps/                                                                │ │
│  │    app-sample/                                                        │ │
│  │      dev.yml       ← release_tag: app-sample-abc1234-20261015120000  │ │
│  │      staging.yml   ← release_tag: app-sample-xyz9999-20261010080000  │ │
│  │      prod.yml      ← release_tag: app-sample-aaa0001-20261001060000  │ │
│  │    app-billing/                                                       │ │
│  │      dev.yml                                                          │ │
│  │      ...                                                              │ │
│  │  .github/workflows/                                                   │ │
│  │    deploy-on-config-change.yml  ← triggered by push to main          │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## End-to-End Flow

```
Developer pushes to app-sample/main
        │
        ▼
[1] ci.yml runs tests
        │
        ▼
[2] ci.yml calls workflows-central/build-artifact.yml
        │
        ▼
[3] build-artifact.yml:
     a. Builds artifact (zip, exe, dll, etc.)
     b. Creates GitHub Release  →  tag: app-sample-abc1234-20261015120000
                                   asset: artifact.zip
     c. Runs open_config_pr.py  →  opens PR on config-repo:
                                   apps/app-sample/dev.yml
                                   release_tag: app-sample-abc1234-20261015120000
        │
        ▼
[4] Human reviews + merges PR on config-repo
     (or auto-merge is enabled for dev)
        │
        ▼
[5] push to config-repo/main triggers deploy-on-config-change.yml
        │
        ▼
[6] Workflow diffs changed files → builds deploy matrix:
     [{app: "app-sample", env: "dev", config: "apps/app-sample/dev.yml"}]
        │
        ▼
[7] For each entry in matrix, on self-hosted runner labelled [self-hosted, dev]:
     a. Reads config file (gets release_tag, deploy_path)
     b. Downloads artifact.zip from GitHub Release
     c. Runs PowerShell deploy script (stop service → extract → start service)
     d. Records GitHub Deployment event
```

---

## Promotion Between Environments

Environments are **not** automatically promoted. To deploy to staging:

1. Edit `config-repo/apps/app-sample/staging.yml` — change `release_tag` to the tag you want
2. Open a PR → triggers required reviewers if configured in GitHub Environments
3. Merge → deploy workflow runs on `[self-hosted, staging]` runner

This is deliberate. The build only auto-promotes to `dev` to keep the feedback loop fast.  Higher environments always require a human decision, equivalent to ADO release pipeline gates.

---

## Scaling to 500 Repos

Every app repo's `ci.yml` is ~20 lines:
```yaml
uses: your-org/workflows-central/.github/workflows/build-artifact.yml@main
with:
  app-name: app-billing
  build-command: "msbuild src/billing.sln /p:Configuration=Release"
secrets:
  CONFIG_REPO_TOKEN: ${{ secrets.CONFIG_REPO_TOKEN }}
```

To change build or release behavior for all 500 repos: edit `workflows-central` once. The `@main` reference means all callers pick up changes immediately (or pin to `@v1` for stability — see [05-versioning.md](05-versioning.md)).

---

## References

- [GitHub Reusable Workflows](https://docs.github.com/en/actions/sharing-automations/reusing-workflows)
- [GitHub Releases API](https://docs.github.com/en/rest/releases/releases)
- [GitHub Environments (approval gates)](https://docs.github.com/en/actions/managing-workflow-runs-and-deployments/managing-deployments/managing-environments-for-deployment)
- [Self-hosted runners](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/about-self-hosted-runners)
- [GitOps principles](https://opengitops.dev/)
