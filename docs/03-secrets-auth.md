# Secrets & Authentication

## Two Auth Problems to Solve

| # | Problem | Solution (POC) | Solution (Production) |
|---|---------|---------------|----------------------|
| 1 | Build workflow in `app-sample` needs to open a PR on `config-repo` | PAT stored as `CONFIG_REPO_TOKEN` secret | GitHub App installation token |
| 2 | Deploy workflow in `config-repo` needs to download a release from `app-sample` | PAT stored as `ARTIFACT_REPO_TOKEN` secret | GitHub App installation token |
| 3 | Deploy workflow needs to authenticate to Azure (2027 migration) | N/A in POC | OIDC federated credential — see [04-azure-oidc.md](04-azure-oidc.md) |

---

## Option A — PAT (Personal Access Token)

What this POC uses. Simple but has operational drawbacks at scale.

### How it works

A PAT is a long-lived credential tied to a specific GitHub user account. It acts as a password for the GitHub API with configurable scopes. In workflows, it's stored as a repo/org secret and injected as an env var.

**ADO equivalent:** PAT or service principal client secret stored as a pipeline variable (secret).

### Limitations at 500 repos

- **Tied to a person:** If the user who created the PAT leaves or gets offboarded, all 500 repo workflows break simultaneously
- **No auto-rotation:** PATs expire and must be manually renewed; fine-grained tokens require a 1-year max
- **Audit trail:** All API calls show as the PAT owner, not the workflow — harder to audit
- **Broad scope risk:** Even fine-grained PATs can't be restricted to specific workflow files within a repo

### Fine-grained PAT scopes for this system

When creating via GitHub → Settings → Developer Settings → Fine-grained tokens:

```
Repository access: Only selected repositories
  ├── config-repo
  └── app-sample

Permissions:
  ├── Contents:       Read and write  (push branch, create release)
  ├── Pull requests:  Read and write  (open PR)
  └── Metadata:       Read (mandatory, auto-selected)
```

---

## Option B — GitHub App (Recommended for Production)

A GitHub App is a first-class machine identity in GitHub. It generates short-lived tokens (1 hour) scoped to specific repos and permissions. No personal account dependency.

**ADO equivalent:** Azure AD service principal with federated credential (managed identity style) — but simpler because GitHub handles all of this natively.

### Why GitHub Apps over PATs

| Attribute | PAT | GitHub App |
|-----------|-----|-----------|
| Tied to a person | Yes — breaks if person leaves | No — belongs to the org |
| Token lifetime | User-set (up to 1 year) | 1 hour — auto-rotated |
| Scope granularity | Repo + permission type | Repo + permission type + installation |
| Audit identity | Shows as the user | Shows as `your-app[bot]` — clearly machine-generated |
| Rate limits | 5,000 req/hr (user) | 5,000 req/hr per install — scales with installs |
| Cost | Free | Free |

### Creating a GitHub App (future production step)

1. **GitHub org** → Settings → Developer settings → GitHub Apps → New GitHub App
2. Set:
   - Name: `gitops-release-promoter`
   - Homepage URL: your internal docs URL
   - Uncheck "Active" on Webhook (you don't need one)
   - Permissions:
     - Repository → Contents: Read and write
     - Repository → Pull requests: Read and write
   - Where can this be installed: Only on this account
3. Click **Create GitHub App** → note the App ID
4. Scroll to "Private keys" → Generate a private key → download `.pem`
5. Click **Install App** → install on `config-repo` and `app-sample`

### Using the App Token in workflows

```yaml
- name: Generate GitHub App token
  id: app-token
  uses: actions/create-github-app-token@v1
  with:
    app-id: ${{ secrets.GH_APP_ID }}
    private-key: ${{ secrets.GH_APP_PRIVATE_KEY }}
    repositories: "config-repo,app-sample"

- name: Open config PR
  env:
    CONFIG_REPO_TOKEN: ${{ steps.app-token.outputs.token }}
  run: python .github/scripts/open_config_pr.py
```

Store `GH_APP_ID` (numeric) and `GH_APP_PRIVATE_KEY` (the `.pem` content) as org-level secrets — then all 500 repos can use the same App without any per-repo secret management.

**References:**
- [actions/create-github-app-token](https://github.com/actions/create-github-app-token)
- [GitHub Apps documentation](https://docs.github.com/en/apps/creating-github-apps/about-creating-github-apps/about-creating-github-apps)

---

## Secret Scopes: Org vs Repo vs Environment

**ADO equivalent of each:**

| GitHub Secret Scope | ADO Equivalent | When to use |
|--------------------|---------------|-------------|
| Organization secret | Variable group shared across all pipelines | Cross-repo credentials (GitHub App keys, shared SPN) |
| Repository secret | Pipeline variable or library scoped to one pipeline | Repo-specific credentials |
| Environment secret | Stage-scoped variable (only accessible when deploying to that env) | Prod credentials that must not be accessible from dev jobs |

### Setting org-level secrets

1. GitHub org → **Settings** → **Secrets and variables** → **Actions** → **New organization secret**
2. Set repository access: "All repositories" or select specific ones
3. Repos can reference these the same way as repo secrets: `${{ secrets.MY_ORG_SECRET }}`

### Environment secrets override repo secrets

If both `config-repo` (repo-level) and the `prod` environment (env-level) define `DEPLOY_KEY`, the environment secret wins when the job targets `environment: prod`. Use this to give prod jobs a more privileged credential than dev jobs.

---

## GITHUB_TOKEN — The Built-in Token

Every workflow run gets an automatic `GITHUB_TOKEN` with no setup required.

**ADO equivalent:** The implicit build service account (e.g., `Project Collection Build Service`).

```yaml
env:
  GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### Default permissions (repo-level setting)

GitHub orgs and repos default to "Restricted permissions" (read-only) or "Read and write". Check:
- Repo → Settings → Actions → General → Workflow permissions

### Limiting permissions per workflow (best practice)

```yaml
permissions:
  contents: write        # upload release assets
  pull-requests: read    # read PR info
  id-token: write        # OIDC — needed for Azure login
```

Setting `permissions:` at the workflow level overrides the repo default for that run. Setting it at the job level is even more granular — a job that only reads doesn't need write access.

### `GITHUB_TOKEN` limitations

- **Cannot push to a protected branch** that has required status checks — because the push itself would need to pass checks, and a token can't approve its own checks
- **Cannot trigger another workflow** — a push made with `GITHUB_TOKEN` does not trigger `on: push` in other workflows. This is intentional to prevent infinite loops. To trigger across repos, use a PAT or GitHub App token
- **Cannot open PRs in other repos** — scoped to the current repo only. This is why `CONFIG_REPO_TOKEN` exists

---

## References

- [GitHub fine-grained PATs](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)
- [GitHub Apps vs PATs](https://docs.github.com/en/apps/creating-github-apps/about-creating-github-apps/deciding-when-to-build-a-github-app)
- [Encrypted secrets](https://docs.github.com/en/actions/security-for-github-actions/security-guides/using-secrets-in-github-actions)
- [GITHUB_TOKEN automatic token](https://docs.github.com/en/actions/security-for-github-actions/security-guides/automatic-token-authentication)
- [actions/create-github-app-token](https://github.com/actions/create-github-app-token)
