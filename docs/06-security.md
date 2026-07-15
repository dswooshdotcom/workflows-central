# Security Hardening

## Self-Hosted Runner Risks

Self-hosted runners are the primary attack surface in this architecture.

### The core risk

A self-hosted runner executes arbitrary code from the workflow. If a malicious PR can trigger a workflow run on a self-hosted runner, the attacker controls what runs on your on-prem host.

**ADO equivalent:** Self-hosted agent security — ADO has the same risk, mitigated by "Demand" filtering and agent pool access controls. GitHub has runner groups.

### Mitigations

**1. Runner groups with repo access control (most important)**

```
GitHub org → Settings → Actions → Runner groups → New group
  Name: "on-prem-runners"
  Repository access: Only selected repositories → [config-repo]
  Allow public repositories: OFF (critical — never allow public repos)
```

Only `config-repo` can use runners in this group. `app-sample` doesn't need the runner — it only runs on GitHub-hosted ubuntu machines.

**2. Deploy only from `config-repo/main`, never from PRs**

The deploy workflow is triggered by `on: push: branches: [main]`. PRs to `config-repo` do NOT trigger deploys. A PR author cannot make the runner execute their code — only merged commits do.

```yaml
on:
  push:
    branches: [main]   # ← only main; NOT pull_request
    paths:
      - "apps/**/*.yml"
```

**ADO equivalent:** Configuring the release pipeline to only trigger from a specific branch, not from PR builds.

**3. Pin action versions to SHAs in security-sensitive workflows**

For workflows that run on self-hosted runners, pin third-party actions to full SHAs:

```yaml
# Instead of:
- uses: actions/checkout@v4

# Use:
- uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683  # v4.2.2
```

This prevents a compromised action tag from executing different code than expected.

**ADO equivalent:** Pinning task versions in ADO (`UsePythonVersion@0` vs `UsePythonVersion@0.230.0`).

**4. Restrict `GITHUB_TOKEN` permissions**

```yaml
permissions:
  contents: read     # minimum needed for checkout
```

Any permission not listed is denied. A workflow that only reads the config file doesn't need `pull-requests: write`.

**5. Don't echo secrets**

```yaml
# BAD — leaks secret to run log
- run: echo "Token is ${{ secrets.MY_TOKEN }}"

# GOOD — pass via environment, GitHub masks the value
- run: python deploy.py
  env:
    TOKEN: ${{ secrets.MY_TOKEN }}
```

GitHub automatically masks known secret values in logs, but the `${{ secrets.X }}` expression in `run:` inline is evaluated before masking.

---

## Branch Protection on `config-repo/main`

`config-repo/main` is the production deployment trigger. Protect it like a prod database.

```
config-repo → Settings → Branches → Add rule → main

✅ Require a pull request before merging
  ✅ Require approvals: 1 (or 2 for prod)
  ✅ Dismiss stale pull request approvals when new commits are pushed
✅ Require status checks to pass before merging
  ✅ Add: "deploy-on-config-change / detect-changes" (so the matrix check must pass)
✅ Require branches to be up to date before merging
✅ Restrict who can push to matching branches: [list specific teams/users]
✅ Do not allow bypassing the above settings
```

**ADO equivalent:** Branch policy with "Require a minimum number of reviewers" + "Require a successful build."

---

## CODEOWNERS for Config Files

```
# config-repo/.github/CODEOWNERS

# Any change to a prod config requires the platform team
apps/*/prod.yml  @dswooshdotcom/platform-team

# Dev and staging configs can be approved by the app team
apps/app-sample/  @dswooshdotcom/app-sample-team
```

CODEOWNERS automatically requests reviews from the right team for the right files. A PR changing `apps/app-sample/prod.yml` pings `platform-team`; one changing `apps/app-sample/dev.yml` pings `app-sample-team`.

**ADO equivalent:** Required reviewer policy with path filters — ADO lets you say "changes to `/prod/*` require approval from these people."

---

## Audit Logging

GitHub org audit log records:
- Workflow runs and their triggers
- Secret access (not the secret value — just that it was accessed)
- Runner registration/deregistration
- Branch protection changes
- Repository permission changes

Access: GitHub org → Settings → Audit log → filter by `action:workflows.*`

For SIEM integration, enable audit log streaming:
- GitHub org → Settings → Audit log → Log streaming
- Supports: Splunk, Azure Event Hubs, Amazon S3, Datadog, Google Cloud Storage

**ADO equivalent:** ADO audit log → Export to Storage. Same concept, different UI.

---

## Supply Chain Security — Workflow File Integrity

When `workflows-central` is the central authority for 500 repos, it's a supply chain target. Mitigations:

**1. Protect the `main` branch of `workflows-central`**
- Require PR + review for any change
- No direct pushes, even for admins

**2. Use `@v1` tags signed with `attest` (future)**
GitHub now supports artifact attestations:
```bash
# In workflows-central release workflow
gh attestation sign --predicate-type build workflows/build-artifact.yml
```
Callers can verify: `gh attestation verify build-artifact.yml`

**3. Dependabot security updates**
Dependabot automatically opens PRs for actions with known CVEs. Enable in GitHub org → Settings → Code security → Dependabot alerts.

---

## SQL Script Deployment Security Note

The company mentioned SQL scripts in `.bat DLL` — likely batch scripts running SQL migrations. Additional mitigations for this case:

- Run SQL deploy steps with a service account that has `db_owner` only on the target database — not `sysadmin`
- Log all SQL executions to a table (`dbo.MigrationHistory` pattern — DbUp and DACPAC both do this)
- Store SQL scripts in a separate sub-directory of `artifacts/` and deploy them in a separate job step after the binary deploy

---

## References

- [GitHub hardening recommendations](https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions)
- [Runner group access controls](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/managing-access-to-self-hosted-runners-using-groups)
- [CODEOWNERS](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners)
- [GitHub artifact attestations](https://docs.github.com/en/actions/security-for-github-actions/using-artifact-attestations/using-artifact-attestations-to-establish-provenance-for-builds)
- [OSSF Scorecard — rate your repo's security posture](https://securityscorecards.dev/)
