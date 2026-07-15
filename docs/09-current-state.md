# Current State — What Was Deployed

This document captures the exact state of the three-repo system as it was initially set up. Update it whenever the infrastructure changes.

---

## Repos

| Repo | URL | Contents |
|------|-----|----------|
| `workflows-central` | https://github.com/dswooshdotcom/workflows-central | Reusable `build-artifact` workflow, `open_config_pr.py` Python script, 9 doc files |
| `app-sample` | https://github.com/dswooshdotcom/app-sample | Sample Python app, pytest tests, `ci.yml` calling the central workflow |
| `config-repo` | https://github.com/dswooshdotcom/config-repo | Per-environment YAML files, deploy workflow, CODEOWNERS, PR template |

---

## What Was Wired Up Automatically

### Secrets

| Secret | Repo | Purpose |
|--------|------|---------|
| `CONFIG_REPO_TOKEN` | `app-sample` | Used by the build workflow to push a branch and open a PR on `config-repo` after a successful release |
| `ARTIFACT_REPO_TOKEN` | `config-repo` | Used by the deploy workflow to download the release asset from the app repo |

Both secrets use the same PAT (the account's stored GitHub credential). For production at 500 repos, replace with a GitHub App token — see [03-secrets-auth.md](03-secrets-auth.md).

### GitHub Environments (on `config-repo`)

| Environment | Protection | Purpose |
|-------------|-----------|---------|
| `dev` | None — auto-deploys on merge | Fast feedback; no human gate |
| `staging` | (add required reviewer manually) | Human approval before staging deploy |
| `prod` | 5-minute wait timer | Time buffer to abort a bad deploy before it runs |

To add required reviewers: `config-repo → Settings → Environments → [env name] → Required reviewers`.

### Branch Protection (on `config-repo/main`)

- Requires a pull request before merging (no direct pushes)
- Requires 1 approving reviewer
- Dismisses stale reviews when new commits are pushed
- Force pushes disabled

**ADO equivalent:** Branch policy with "Require a minimum number of reviewers" + dismiss stale approvals.

### Workflow Permissions

| Repo | Setting | Why |
|------|---------|-----|
| `app-sample` | Read and write | `GITHUB_TOKEN` needs write to create releases and push tags |
| `workflows-central` | Read and write | Same — the reusable workflow runs in the caller's context, but the central repo's permissions matter for the release step |

Set at: `repo → Settings → Actions → General → Workflow permissions`.

---

## What Still Needs to Be Done to Complete the Loop

### 1. Register a Self-Hosted Windows Runner (Required for deploys)

The deploy workflow targets `runs-on: [self-hosted, dev]`. Without a registered runner, deploy jobs queue indefinitely and never execute.

Full setup instructions: [08-self-hosted-runners.md](08-self-hosted-runners.md)

Quick version:
1. On your on-prem Windows host, open PowerShell as Administrator
2. Go to `config-repo → Settings → Actions → Runners → New self-hosted runner`
3. Select Windows, follow the download + `config.cmd` commands
4. When prompted for labels: enter `dev`
5. Run `./svc.cmd install && ./svc.cmd start`
6. Verify: runner appears as **Idle** in GitHub UI

Repeat for `staging` and `prod` with the appropriate label.

### 2. Approve the `softprops/action-gh-release` Third-Party Action

The `build-artifact.yml` workflow uses `softprops/action-gh-release@v2` to create GitHub Releases. GitHub requires org/repo owners to explicitly permit third-party actions.

Two options:

**Option A — Permit all actions (simplest for a personal account):**
```
app-sample → Settings → Actions → General → Actions permissions
→ "Allow all actions and reusable workflows"
```

**Option B — Allow specific actions only (recommended for org):**
```
org → Settings → Actions → General → Actions permissions
→ "Allow dswooshdotcom, and select non-dswooshdotcom, actions and reusable workflows"
→ Add: softprops/action-gh-release@*
```

**Option C — Replace with `gh release create` (no third-party dependency):**

Replace the `softprops/action-gh-release` step in `build-artifact.yml` with:
```yaml
- name: Create GitHub Release
  id: release
  env:
    GH_TOKEN: ${{ github.token }}
  run: |
    TAG="${{ steps.tag.outputs.tag }}"
    gh release create "$TAG" \
      "${{ inputs.artifact-path }}" \
      --title "${{ inputs.app-name }} $TAG" \
      --generate-notes
    echo "url=https://github.com/${{ github.repository }}/releases/tag/$TAG" >> "$GITHUB_OUTPUT"
```

This uses only the built-in `GITHUB_TOKEN` — no third-party action, no acceptance required. The tradeoff: slightly less metadata in the release (no auto-generated notes from the Releases API — though `--generate-notes` approximates it).

### 3. Test the End-to-End Flow

Once the runner is registered and action permissions are set:

1. Make any change to `app-sample/src/app.py` and push to `main`
2. Watch `app-sample → Actions` — CI runs → build → release created
3. Watch `config-repo → Pull requests` — PR appears updating `apps/app-sample/dev.yml`
4. Merge the PR
5. Watch `config-repo → Actions` — deploy workflow fires on the `dev` runner
6. Check `config-repo → Environments` — `dev` shows the latest deployment

---

## Adding the Next App (Checklist)

When onboarding a real app from the 500-repo migration:

```
Developer:
  ☐ Add .github/workflows/ci.yml (copy from app-sample, change app-name + build-command)
  ☐ Confirm CONFIG_REPO_TOKEN secret is accessible (org secret or per-repo)

Platform team:
  ☐ Create apps/<app-name>/dev.yml in config-repo
  ☐ Create apps/<app-name>/staging.yml
  ☐ Create apps/<app-name>/prod.yml
  ☐ Merge config-repo PR adding those files
  ☐ Verify deploy_path exists on the runner host
```

Full guide: [07-adding-a-new-app.md](07-adding-a-new-app.md)
