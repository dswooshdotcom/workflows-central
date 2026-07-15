# Workflow Versioning — Pinning vs Floating

When 500 repos call `workflows-central`, the version ref they use determines how changes roll out.

---

## Three Ref Strategies

### 1. Float on `@main` (what this POC uses)

```yaml
uses: dswooshdotcom/workflows-central/.github/workflows/build-artifact.yml@main
```

- **Pros:** All repos get fixes and improvements instantly. No per-repo update PRs.
- **Cons:** A breaking change in `workflows-central` breaks all 500 repos simultaneously.
- **When to use:** Early stages, single team, high trust in `workflows-central` maintainers.

**ADO equivalent:** Referencing a YAML template by branch rather than a specific commit — uncommon in ADO because ADO templates are typically in the same repo.

### 2. Pin to a tag / release (`@v1`, `@v1.2.3`)

```yaml
uses: dswooshdotcom/workflows-central/.github/workflows/build-artifact.yml@v1
```

- **Pros:** Breaking changes in `workflows-central` don't affect existing callers. Callers opt in to upgrades.
- **Cons:** Callers accumulate drift. Security fixes require all 500 repos to update their ref.
- **When to use:** Stable, versioned platform. Multiple teams consuming the workflow with different upgrade cadences.

### 3. Pin to a commit SHA

```yaml
uses: dswooshdotcom/workflows-central/.github/workflows/build-artifact.yml@a1b2c3d4
```

- **Pros:** Maximum reproducibility. Nothing changes unless you explicitly update the SHA.
- **Cons:** You will never get security fixes unless you actively update.
- **When to use:** Highly regulated environments where every build must be bit-for-bit reproducible. Overkill for most cases.

---

## Versioning `workflows-central` with Tags

When you're ready to move from `@main` to semantic versioning:

```bash
# In workflows-central
git tag v1.0.0
git push origin v1.0.0

# After a breaking change
git tag v2.0.0
git push origin v2.0.0
```

Create a GitHub Release for each tag — gives callers a changelog to read before upgrading.

### Moving tags (mutable `@v1` pointer)

The `@v1` pattern (major version tag) lets you push patches without requiring callers to update:

```bash
# After patching v1.x.y
git tag -f v1               # move the v1 tag to the new commit
git push origin v1 --force  # force-push the tag
```

This is how `actions/checkout@v4` works — `v4` always points to the latest `4.x.y` patch. Callers reference `@v4` and automatically get bug fixes.

**ADO equivalent:** YAML template versioning — ADO templates don't have a native version concept; teams use branch naming conventions (`templates/v1`, `templates/v2`) to achieve the same effect. GitHub's tag ref is cleaner.

---

## Dependabot for Keeping Refs Current

Add this to `app-sample/.github/dependabot.yml` to get automatic PRs when `workflows-central` releases a new version or when actions have updates:

```yaml
version: 2
updates:
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
    labels:
      - "dependencies"
      - "github-actions"
```

Dependabot opens PRs like: `Bump dswooshdotcom/workflows-central from v1.2.0 to v1.3.0`. You review and merge. At 500 repos, this is how you manage the upgrade surface.

**ADO equivalent:** No native equivalent in ADO — teams typically handle template updates manually or with custom scripts.

---

## Required Workflows (Org-Level Enforcement)

If you want to mandate that ALL repos run `build-artifact.yml` regardless of what's in their `ci.yml`, GitHub has a native enforcement mechanism:

1. GitHub org → **Settings** → **Actions** → **Required workflows**
2. Add `workflows-central/.github/workflows/build-artifact.yml@main`
3. Apply to: "All repositories" or specific repos

When configured, this workflow runs on every push/PR in every targeted repo, even if the repo doesn't call it. The workflow run appears as a required status check — PRs can't merge if it fails.

**ADO equivalent:** "Required YAML template" with `extends:` enforcement — where ADO org admins can mandate that all pipelines extend a specific template. GitHub's required workflows are the direct equivalent.

> This is the most powerful tool for the 500-repo migration. Instead of updating every repo's `ci.yml`, you configure org-level enforcement and the central workflow runs everywhere.

---

## References

- [Reusable workflow `uses:` syntax](https://docs.github.com/en/actions/sharing-automations/reusing-workflows#calling-a-reusable-workflow)
- [Required workflows](https://docs.github.com/en/actions/managing-workflow-runs-and-deployments/managing-workflow-runs/required-workflows)
- [Dependabot for Actions](https://docs.github.com/en/code-security/dependabot/working-with-dependabot/keeping-your-actions-up-to-date-with-dependabot)
- [GitHub Actions versioning best practices](https://docs.github.com/en/actions/sharing-automations/creating-actions/releasing-and-maintaining-actions)
