# Setup Guide — Step by Step

Everything needed to go from zero to a working end-to-end deploy. Each step includes the ADO equivalent for orientation.

---

## Prerequisites

- GitHub organization or personal account (this POC uses `dswooshdotcom`)
- GitHub PAT with `repo` scope — see [Secrets & Auth](03-secrets-auth.md)
- On-premises Windows host to register as a self-hosted runner
- Python 3.10+ on the runner host (`py` or `python3`)
- PowerShell 5.1+ on the runner host (built into Windows Server 2016+)

---

## Step 1 — Create the Three Repos

### On GitHub.com

1. Go to **github.com/new**
2. Create three repos (public or private — private recommended for production):
   - `workflows-central` — initialize with a README
   - `app-sample` — initialize with a README
   - `config-repo` — initialize with a README

**ADO equivalent:** Creating three separate Azure Repos within a project.

---

## Step 2 — Push Repo Contents

Each folder in this POC maps to one GitHub repo.

```bash
# workflows-central
cd ~/Desktop/gitops-poc/workflows-central
git init
git remote add origin https://github.com/dswooshdotcom/workflows-central.git
git add .
git commit -m "feat: initial reusable build-artifact workflow and docs"
git branch -M main
git push -u origin main

# app-sample
cd ~/Desktop/gitops-poc/app-sample
git init
git remote add origin https://github.com/dswooshdotcom/app-sample.git
git add .
git commit -m "feat: sample app with ci.yml calling central build workflow"
git branch -M main
git push -u origin main

# config-repo
cd ~/Desktop/gitops-poc/config-repo
git init
git remote add origin https://github.com/dswooshdotcom/config-repo.git
git add .
git commit -m "feat: initial environment config for app-sample"
git branch -M main
git push -u origin main
```

---

## Step 3 — Create a PAT (Personal Access Token)

The build workflow needs to open PRs on `config-repo`, and the deploy workflow needs to download artifacts from `app-sample`. One PAT can cover both.

**ADO equivalent:** A service connection using a service principal with "Contributor" on the repo, or a PAT with "Code (Read & Write)".

### Create the PAT

1. GitHub → top-right avatar → **Settings**
2. Left sidebar → **Developer settings** → **Personal access tokens** → **Fine-grained tokens**
3. Click **Generate new token**
4. Set name: `gitops-poc-ci`
5. Set expiration: 90 days (or set a calendar reminder to rotate)
6. Under **Repository access** → select **Only select repositories** → pick `config-repo` and `app-sample`
7. Under **Permissions**:
   - **Contents**: Read and write (create releases, push branches)
   - **Pull requests**: Read and write (open PRs)
   - **Metadata**: Read (required by GitHub — cannot be deselected)
8. Click **Generate token** — copy it immediately, you won't see it again

**Store it somewhere safe** (1Password, etc.) — you'll need it in the next two steps.

> For production at 500 repos: replace the PAT with a GitHub App. A GitHub App token is scoped to specific repos, auto-rotates every hour, and doesn't expire or get revoked when an employee leaves. See [03-secrets-auth.md](03-secrets-auth.md).

---

## Step 4 — Add Secrets to Repos

### `app-sample` → `CONFIG_REPO_TOKEN`

The build workflow uses this to push a branch and open a PR on `config-repo`.

1. Go to `github.com/dswooshdotcom/app-sample`
2. **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `CONFIG_REPO_TOKEN`
5. Value: paste the PAT from Step 3
6. Click **Add secret**

**ADO equivalent:** Pipeline variable (secret) — the lock icon in the Variables tab.

### `config-repo` → `ARTIFACT_REPO_TOKEN`

The deploy workflow uses this to download the release asset from `app-sample`.

1. Go to `github.com/dswooshdotcom/config-repo`
2. **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `ARTIFACT_REPO_TOKEN`
5. Value: paste the same PAT
6. Click **Add secret**

---

## Step 5 — Configure GitHub Environments

Environments in GitHub are the gate mechanism equivalent to ADO release pipeline approvals.

**ADO equivalent:** Release pipeline stage with "Pre-deployment approvals" enabled.

### Create the `dev` environment (auto-deploy, no approvals)

1. Go to `github.com/dswooshdotcom/config-repo`
2. **Settings** → **Environments** → **New environment**
3. Name: `dev`
4. Click **Configure environment**
5. Leave "Required reviewers" empty (dev auto-deploys on merge)
6. Under "Deployment branches and tags": restrict to `main` branch only

### Create the `staging` environment

1. Same steps, name: `staging`
2. Add yourself as a required reviewer
3. Restrict to `main` branch

### Create the `prod` environment

1. Same steps, name: `prod`
2. Add required reviewers (yourself + at least one other)
3. Enable "Wait timer": 5 minutes (gives reviewers time to notice and abort)
4. Restrict to `main` branch

---

## Step 6 — Register a Self-Hosted Runner

The deploy workflow targets `[self-hosted, dev]`. You need at least one runner with that label.

**ADO equivalent:** Self-hosted agent registered to an agent pool. In ADO you download and configure `config.cmd` — GitHub is identical.

### On the on-premises Windows host

1. Go to `github.com/dswooshdotcom/config-repo`
2. **Settings** → **Actions** → **Runners** → **New self-hosted runner**
3. Select OS: **Windows**
4. Follow the displayed commands in PowerShell:

```powershell
# Download
mkdir actions-runner; cd actions-runner
# (copy the exact download URL from the GitHub UI — it's versioned)
Invoke-WebRequest -Uri https://github.com/actions/runner/releases/download/v2.xxx/actions-runner-win-x64-2.xxx.zip -OutFile actions-runner-win-x64.zip
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::ExtractToDirectory("$PWD/actions-runner-win-x64.zip", "$PWD")

# Configure — this registers the runner with your repo
./config.cmd --url https://github.com/dswooshdotcom/config-repo --token RUNNER_TOKEN_FROM_UI

# Add extra labels during setup (or via UI afterward)
# When prompted for labels: enter "dev" (or "staging", "prod" for other runners)

# Install as Windows Service so it survives reboots
./svc.cmd install
./svc.cmd start
```

5. Verify: back on GitHub, the runner appears as **Idle** in Settings → Actions → Runners

> **Security note:** Never register a self-hosted runner on a public repo. Self-hosted runners on public repos can be triggered by any fork's pull request, which is a known attack vector. Restrict to private repos or use runner groups with repo access controls. See [06-security.md](06-security.md).

---

## Step 7 — Verify the End-to-End Flow

1. Make a trivial change to `app-sample/src/app.py` (e.g., change the greeting string)
2. Push to `main`
3. Watch **Actions** tab on `app-sample` — the `CI / Build & Release` workflow runs
4. After ~60 seconds: check **Releases** on `app-sample` — a new release appears
5. Check **Pull requests** on `config-repo` — a PR appears: `[app-sample] Deploy app-sample-... to dev`
6. Merge the PR
7. Watch **Actions** tab on `config-repo` — `Deploy on Config Change` workflow fires
8. The workflow identifies the changed file, pulls the artifact, runs the deploy step
9. Check **Environments** on `config-repo`'s home page — `dev` shows the latest deployment

---

## Troubleshooting

### "Resource not accessible by integration" on PR creation

The `CONFIG_REPO_TOKEN` doesn't have pull-request write permission. Re-check Step 3 — ensure "Pull requests: Read and write" is selected in the fine-grained PAT.

### Deploy workflow doesn't trigger

Check that `deploy-on-config-change.yml` has `paths: - "apps/**/*.yml"` and the merged file matches. Also verify the workflow isn't disabled in Actions settings.

### Runner shows as "Offline"

The runner service stopped. On the Windows host: `Services.msc` → find `GitHub Actions Runner (config-repo.actions-runner...)` → Start. Or: `./svc.cmd start` in the runner directory.

### "No releases found" when downloading artifact

The release tag in `dev.yml` doesn't match a real release. Check `app-sample` → Releases and compare tags.
