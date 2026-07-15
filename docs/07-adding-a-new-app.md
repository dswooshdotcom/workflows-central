# Onboarding a New App

How to add a new application to the GitOps system. This is the playbook you'll hand to developers during the 500-repo migration.

---

## What the Developer Does (in their app repo)

### 1. Add `.github/workflows/ci.yml`

Replace `app-billing` with their app name:

```yaml
name: CI / Build & Release

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - run: python -m pytest tests/

  build-and-promote:
    needs: test
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    uses: dswooshdotcom/workflows-central/.github/workflows/build-artifact.yml@main
    with:
      app-name: app-billing          # ← change this
      build-command: |               # ← change this to whatever builds your artifact
        zip -r artifact.zip src/
      config-repo: dswooshdotcom/config-repo
    secrets:
      CONFIG_REPO_TOKEN: ${{ secrets.CONFIG_REPO_TOKEN }}
```

### 2. Add `CONFIG_REPO_TOKEN` secret to their repo

Settings → Secrets and variables → Actions → New repository secret
- Name: `CONFIG_REPO_TOKEN`
- Value: the org-level PAT (or, better, a GitHub App token)

> **If using org-level secrets:** The platform team can store `CONFIG_REPO_TOKEN` as an org secret accessible to all repos. Then developers don't need to add any secrets at all.

---

## What the Platform Team Does (in config-repo)

### 3. Add config files for the new app

```bash
mkdir -p config-repo/apps/app-billing
```

Create three files:

**`apps/app-billing/dev.yml`**
```yaml
environment: dev
artifact_repo: app-billing
deploy_path: "C:\\Apps\\app-billing"
release_tag: ""
last_promoted_by: ""
last_promoted_sha: ""
```

Repeat for `staging.yml` and `prod.yml`, changing `environment:` and `deploy_path:` as needed.

### 4. Open a PR on config-repo to add these files

The PR itself doesn't trigger a deploy (no existing `release_tag`) — it just registers the app in the system. Once the developer's first build completes, the auto-PR will populate `release_tag: app-billing-abc1234-...`.

---

## What Happens on First Push

1. Developer pushes code to `app-billing/main`
2. CI runs tests → build → creates Release `app-billing-abc1234-20261020`
3. `open_config_pr.py` opens PR on `config-repo`: sets `apps/app-billing/dev.yml` `release_tag`
4. Platform team (or auto-merge) merges the PR
5. Deploy workflow fires on the `[self-hosted, dev]` runner for `app-billing`

---

## Build Command Examples

Different artifact types require different build commands:

### Python zip

```yaml
build-command: |
  pip install -r requirements.txt -t src/__deps__
  zip -r artifact.zip src/ -x "**/__pycache__/*"
```

### .NET / MSBuild (Windows runner needed)

```yaml
runs-on: windows-latest  # override in ci.yml if needed
build-command: |
  msbuild src/MyApp.sln /p:Configuration=Release /p:OutputPath=dist/
  Compress-Archive -Path dist/* -DestinationPath artifact.zip
```

### Batch DLL / native exe

```yaml
build-command: |
  # Assumes a Makefile or build.bat exists
  cmd /c build.bat
  zip artifact.zip dist/*.exe dist/*.dll
```

### SQL scripts (DACPAC)

```yaml
build-command: |
  # Build DACPAC with sqlpackage
  sqlpackage /Action:Extract /SourceServerName:. /SourceDatabaseName:MyDb \
    /TargetFile:artifact.dacpac
  zip -r artifact.zip artifact.dacpac migrations/*.sql
```

Set `artifact-path: artifact.zip` in the `with:` block.

---

## Checklist

```
App team:
  ☐ ci.yml added to app repo
  ☐ CONFIG_REPO_TOKEN secret added (or org secret confirmed accessible)
  ☐ build-command produces artifact.zip (tested locally)
  ☐ tests pass locally

Platform team:
  ☐ apps/<app-name>/dev.yml added to config-repo
  ☐ apps/<app-name>/staging.yml added to config-repo
  ☐ apps/<app-name>/prod.yml added to config-repo
  ☐ config-repo PR merged
  ☐ Self-hosted runner for [dev] registered and Idle
  ☐ deploy_path on runner host created (or confirmed exists)
```

---

## Common Issues

### "Can't find app in config-repo" (PR opens but config file doesn't exist)

`open_config_pr.py` will throw a 404 from the GitHub API when trying to read the config file. Fix: ensure the platform team added `apps/<app-name>/dev.yml` before the first build.

### The deploy path doesn't exist on the runner host

```powershell
# On the runner host
New-Item -ItemType Directory -Force -Path "C:\Apps\app-billing"
```

Or add this to the deploy step:
```powershell
if (-not (Test-Path $env:DEPLOY_PATH)) { New-Item -ItemType Directory $env:DEPLOY_PATH }
```

### Build succeeds but no release appears

Check that the `build-command` produces a file matching `artifact-path` (default: `artifact.zip`) in the workspace root. Use `ls -la` as a debug step:
```yaml
- name: Debug — list workspace
  run: ls -la
  if: always()
```
