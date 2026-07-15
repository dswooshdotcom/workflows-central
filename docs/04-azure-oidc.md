# Azure + OIDC — The 2027 Migration Path

When on-prem deployments move to Azure App Service or Container Apps, the PowerShell extract-and-copy deploy step is replaced with an Azure CLI/Bicep deployment. The auth mechanism changes from "a self-hosted runner with filesystem access" to OIDC federated credentials — no stored secrets.

---

## Why OIDC Instead of a Service Principal + Secret

**ADO equivalent:** ADO service connection using "Workload identity federation" (the modern option) vs. "Service principal (automatic)" with a client secret.

| Method | How it works | Expiry | Secret stored? |
|--------|-------------|--------|---------------|
| SPN + client secret | App registers in Entra ID; secret stored in pipeline vars | Secret expires (1-2 years) | Yes — in ADO variable group or GitHub secret |
| SPN + cert | Same, cert in Key Vault | Cert expires | No plain secret, but cert management required |
| OIDC federated credential | GitHub's OIDC provider issues a short-lived JWT; Azure trusts it | 1 hour, auto-issued | **No** — nothing to rotate or store |

OIDC is what ADO calls "Workload identity federation" when you create a service connection. GitHub Actions has the same mechanism.

---

## How OIDC Works (Step by Step)

```
GitHub Actions runner                 Azure (Entra ID)
        │                                    │
        │   1. Request OIDC token            │
        │ ──────────────────────────────>    │
        │   (JWT signed by github.com)       │
        │                                    │
        │   2. az login --federated-token    │
        │ ──────────────────────────────>   Entra verifies:
        │                                   - Issuer = https://token.actions.githubusercontent.com
        │                                   - Subject = repo:org/repo:ref:refs/heads/main
        │                                   - Audience = api://AzureADTokenExchange
        │                                   - Expiry < 1 hour
        │                                    │
        │   3. Azure access token            │
        │ <──────────────────────────────    │
        │                                    │
        │   4. az webapp deploy ...          │
        │ ──────────────────────────────>   Azure Resource Manager
```

No credentials leave your Azure subscription. The runner never holds a long-lived secret.

---

## Setup in Azure

### 1. Create a Service Principal (App Registration)

```bash
# In Azure Cloud Shell or local az CLI
az ad app create --display-name "github-gitops-deploy"
# Note the appId (client ID) from output

az ad sp create --id <appId>
# Note the id (object ID) from output

# Grant the SP "Contributor" on a specific resource group
az role assignment create \
  --assignee <appId> \
  --role "Contributor" \
  --scope "/subscriptions/<sub-id>/resourceGroups/rg-prod"
```

**ADO equivalent:** Creating a service connection in ADO — ADO does this step automatically if you use "Automatic" service connection creation. With GitHub you do it once per environment manually (or via Terraform/Bicep for 500-repo scale).

### 2. Add the Federated Credential

This tells Entra ID to trust JWTs from GitHub for a specific repo and branch/environment.

```bash
az ad app federated-credential create \
  --id <appId> \
  --parameters '{
    "name": "github-config-repo-prod",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:dswooshdotcom/config-repo:environment:prod",
    "audiences": ["api://AzureADTokenExchange"]
  }'
```

The `subject` field is critical — it pins the trust to:
- A specific repo: `repo:dswooshdotcom/config-repo`
- A specific environment: `environment:prod`

Change `:environment:prod` to `:ref:refs/heads/main` to trust any push to main (less restrictive).

**ADO equivalent:** The "Federated credential" tab in the App Registration when setting up a workload identity service connection.

### 3. Store Three Non-Secret Values in GitHub

These are not secrets (they're tenant/app IDs — public information), but storing them as secrets prevents hardcoding them.

| GitHub Secret Name | Value | ADO Equivalent |
|---|---|---|
| `AZURE_CLIENT_ID` | App Registration's Application (client) ID | Service connection client ID |
| `AZURE_TENANT_ID` | Your Entra ID tenant ID | Tenant ID in service connection |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription ID | Subscription in service connection |

Set these as org-level secrets so all repos can use them without per-repo setup.

---

## Updated Deploy Step (2027 version)

Replace the PowerShell extract block in `deploy-on-config-change.yml` with:

```yaml
- name: Azure login (OIDC — no stored secrets)
  uses: azure/login@v2
  with:
    client-id: ${{ secrets.AZURE_CLIENT_ID }}
    tenant-id: ${{ secrets.AZURE_TENANT_ID }}
    subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}

- name: Deploy to Azure App Service
  run: |
    az webapp deploy \
      --resource-group "rg-${{ matrix.target.env }}" \
      --name "${{ matrix.target.app }}-${{ matrix.target.env }}" \
      --src-path ./artifact/artifact.zip \
      --type zip

- name: Verify deployment
  run: |
    az webapp show \
      --resource-group "rg-${{ matrix.target.env }}" \
      --name "${{ matrix.target.app }}-${{ matrix.target.env }}" \
      --query "state" -o tsv
```

The runner no longer needs to be self-hosted — GitHub-hosted runners can authenticate to Azure via OIDC. Self-hosted runners are only needed for on-prem access.

---

## Required workflow `permissions:` for OIDC

```yaml
permissions:
  id-token: write   # ← MUST be present; allows runner to request OIDC token
  contents: read
```

Without `id-token: write`, the `azure/login` action fails with "Error: AADSTS700016: Application not found."

**ADO equivalent:** No explicit permission needed in ADO — it's handled by the service connection automatically. This is the one place GitHub requires an extra explicit step.

---

## Key Vault Integration

Once OIDC is working, apps can pull Key Vault secrets directly:

```yaml
- uses: azure/login@v2
  with:
    client-id: ${{ secrets.AZURE_CLIENT_ID }}
    tenant-id: ${{ secrets.AZURE_TENANT_ID }}
    subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}

- uses: azure/get-keyvault-secrets@v1
  with:
    keyvault: "kv-prod-myapp"
    secrets: "db-connection-string, stripe-key"
  id: kvSecrets

- run: |
    echo "DB=${{ steps.kvSecrets.outputs.db-connection-string }}" >> $GITHUB_ENV
```

**ADO equivalent:** ADO Key Vault variable group linked to Azure Key Vault. Same concept — inject secrets from Key Vault into the pipeline without storing them in GitHub.

---

## Azure App Configuration

The company mentioned "Azure Config" in their workflow. That's likely Azure App Configuration, which stores non-secret app settings and feature flags.

```bash
# In deploy step, push the release tag to App Config so the app knows its version
az appconfig kv set \
  --name "appconfig-prod" \
  --key "app-sample:release-tag" \
  --value "${{ steps.cfg.outputs.release_tag }}" \
  --yes
```

**ADO equivalent:** Updating an App Configuration store from a release pipeline — identical concept.

---

## References

- [azure/login action](https://github.com/Azure/login)
- [GitHub OIDC token claims](https://docs.github.com/en/actions/security-for-github-actions/security-hardening-your-deployments/about-security-hardening-with-openid-connect)
- [Entra ID workload identity federation](https://learn.microsoft.com/en-us/entra/workload-id/workload-identity-federation)
- [azure/get-keyvault-secrets](https://github.com/Azure/get-keyvault-secrets)
- [Azure App Configuration](https://learn.microsoft.com/en-us/azure/azure-app-configuration/overview)
