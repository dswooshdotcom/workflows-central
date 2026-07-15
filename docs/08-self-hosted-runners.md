# Self-Hosted Runners — On-Prem Windows Setup

Everything needed to register and maintain Windows runners for the on-prem deployment phase.

---

## Why Self-Hosted (vs GitHub-Hosted)

GitHub-hosted runners (`runs-on: windows-latest`) spin up in Azure — they have no access to your on-prem network, file shares, or internal deployment targets. Self-hosted runners run on your hardware inside your network.

**ADO equivalent:** Self-hosted agents registered to a private agent pool. The setup process is nearly identical — download a zip, run `config.cmd`, start the service.

---

## Runner Architecture for This System

```
GitHub (cloud)
  └─ config-repo: deploy-on-config-change.yml
       └─ job: runs-on: [self-hosted, dev]
                    │
              ──────┼──── network boundary ────
                    │
           On-prem Windows host
             └─ GitHub Actions Runner service
                  ├─ Label: self-hosted
                  ├─ Label: dev          ← environment label
                  └─ Label: windows      ← OS label (auto-added)
```

One runner per environment per physical host (or per environment, if hosts are shared).

---

## Installation (Windows)

### PowerShell (as Administrator)

```powershell
# 1. Create a dedicated service account for the runner (recommended)
#    Don't run the runner as Local System or your own account
# net user github-runner StrongPassword123! /add
# net localgroup "Log on as a service" github-runner /add

# 2. Create the runner directory
$runnerDir = "C:\runners\config-repo-dev"
New-Item -ItemType Directory -Force -Path $runnerDir
Set-Location $runnerDir

# 3. Download the runner (get the exact URL from GitHub UI)
#    config-repo → Settings → Actions → Runners → New self-hosted runner → Windows
$runnerVersion = "2.321.0"   # replace with current version from GitHub UI
$downloadUrl = "https://github.com/actions/runner/releases/download/v$runnerVersion/actions-runner-win-x64-$runnerVersion.zip"
Invoke-WebRequest -Uri $downloadUrl -OutFile "actions-runner.zip"
Expand-Archive -Path "actions-runner.zip" -DestinationPath . -Force
Remove-Item "actions-runner.zip"

# 4. Configure (token comes from GitHub UI — expires after 1 hour)
.\config.cmd `
  --url https://github.com/dswooshdotcom/config-repo `
  --token <REGISTRATION_TOKEN_FROM_UI> `
  --name "onprem-dev-01" `
  --labels "dev,windows,onprem" `
  --work "_work" `
  --runasservice `
  --windowslogonaccount "NT AUTHORITY\NETWORK SERVICE"
  # or use a service account: --windowslogonaccount "DOMAIN\github-runner" --windowslogonpassword "..."

# 5. Start the service (config.cmd --runasservice does this, but if manual:)
.\svc.cmd install
.\svc.cmd start
```

### Verify

```powershell
Get-Service -Name "actions.runner.*" | Select-Object Name, Status
# Should show: Running
```

Back on GitHub: `config-repo → Settings → Actions → Runners` — runner appears as **Idle**.

---

## Runner Labels

Labels are how the workflow targets the right runner. The deploy workflow uses:

```yaml
runs-on: [self-hosted, "${{ matrix.target.env }}"]
```

So a `dev` runner needs labels: `self-hosted, dev, windows`  
A `staging` runner needs: `self-hosted, staging, windows`  
A `prod` runner needs: `self-hosted, prod, windows`

Add/edit labels after registration:
- GitHub UI: `config-repo → Settings → Actions → Runners → [runner name] → Edit`
- Or re-run `config.cmd` with `--labels` (removes old labels)

---

## Runner Groups (Multi-Repo Hardening)

By default, a self-hosted runner is available to the repo it's registered under. For org-level runners (runners registered at the org level, available to multiple repos):

1. GitHub org → Settings → Actions → Runner groups → New group
2. Name: `on-prem-windows`
3. Repository access: `Only selected repositories` → select `config-repo`
4. Register the runner to the org, not a specific repo: use the org's runner registration token

This ensures the on-prem runner only runs jobs from `config-repo` — not from any other repo that might be compromised.

**ADO equivalent:** Agent pool with access control — configure which pipelines can use the pool.

---

## Keeping Runners Updated

Runner software updates regularly. Without updates, GitHub eventually stops accepting jobs from outdated runners.

### Automatic updates (default)

Runners auto-update before each job if a new version is available. Requires internet access to `github.com/actions/runner/releases`.

### Disable auto-update (air-gapped environments)

```powershell
.\config.cmd --disableupdate
```

Then manually update by downloading the new ZIP and re-running `config.cmd`.

**ADO equivalent:** "Update agent" button in ADO Agent Pool UI, or agent auto-update via VSTS agent updater.

---

## Multiple Runners for Parallel Deploys

If you're deploying multiple apps simultaneously (matrix strategy), a single runner becomes a bottleneck — only one job runs at a time per runner.

Solution: register multiple runners on the same host:

```powershell
# Register a second runner in a different directory
$runnerDir2 = "C:\runners\config-repo-dev-02"
New-Item -ItemType Directory -Force -Path $runnerDir2
Set-Location $runnerDir2
# Same config.cmd, different --name
.\config.cmd --url ... --token ... --name "onprem-dev-02" --labels "dev,windows"
```

Each runner is its own Windows service. Two runners → two parallel deploys.

**ADO equivalent:** Running multiple agent instances on the same machine — ADO supports this with separate agent directories and service names.

---

## Maintenance & Monitoring

### Check runner logs

```powershell
# Runner logs
Get-EventLog -LogName Application -Source "GitHub Actions*" -Newest 50

# Or in the runner directory
Get-Content "C:\runners\config-repo-dev\_diag\Runner_*.log" -Tail 100
```

### Service recovery settings

```powershell
# Auto-restart the runner service if it crashes
sc.exe failure "actions.runner.dswooshdotcom-config-repo.onprem-dev-01" `
  reset=86400 actions=restart/10000/restart/30000/restart/60000
```

**ADO equivalent:** Configuring Windows Service recovery actions for the Azure Pipelines Agent service.

### Health check endpoint (GitHub's runner API)

```bash
# Check runner status via GitHub API
gh api orgs/dswooshdotcom/actions/runners \
  --jq '.runners[] | {name, status, busy, labels: [.labels[].name]}'
```

---

## References

- [GitHub self-hosted runner docs](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/about-self-hosted-runners)
- [Runner groups](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/managing-access-to-self-hosted-runners-using-groups)
- [Actions Runner Controller (Kubernetes autoscaling)](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners-with-actions-runner-controller/about-actions-runner-controller)
- [Self-hosted runner security hardening](https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions#hardening-for-self-hosted-runners)
