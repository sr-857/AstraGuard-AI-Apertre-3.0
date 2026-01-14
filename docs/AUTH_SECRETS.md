# Auth & Secrets Management

This document describes AstraGuard-AI's secrets management architecture, migration guide, and operational runbooks.

## Quick Start

### Local Development

1. **Copy the environment template:**
   ```bash
   cp config/.env.example .env
   ```

2. **Edit `.env` with your secrets:**
   ```bash
   # .env
   API_KEY=your_api_key_here
   JWT_SECRET=your_jwt_secret_here
   DATABASE_URL=postgres://user:pass@localhost/db
   ```

3. **Use secrets in your code:**
   ```python
   from security.secrets_adapter import get_secret
   
   api_key = get_secret("API_KEY")
   ```

4. **Use secrets in configuration files:**
   ```yaml
   # config/app.yaml
   api:
     key: secrets://API_KEY
     url: https://api.example.com
   ```

   ```python
   from config.config_loader import load_config_with_secrets
   
   config = load_config_with_secrets("config/app.yaml")
   print(config["api"]["key"])  # Prints actual API key
   ```

---

## Architecture

### Adapter Pattern

The secrets system uses a pluggable adapter pattern:

```
┌─────────────────────┐
│   Application Code  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   SecretsAdapter    │  ← Abstract Protocol
│   (get_secret)      │
└──────────┬──────────┘
           │
    ┌──────┴──────┬──────────────┐
    ▼             ▼              ▼
┌───────────┐ ┌───────────┐ ┌────────────┐
│DevFileAdapter│ │VaultAdapter│ │AWSSecretsAdapter│
│ (.env file)│ │ (HashiCorp)│ │ (AWS SM)   │
└───────────┘ └───────────┘ └────────────┘
```

### Available Adapters

| Adapter | Use Case | Configuration |
|---------|----------|---------------|
| `DevFileAdapter` | Local development | Reads from `.env` file |
| `VaultAdapter` | Production (self-hosted) | HashiCorp Vault KV v2 |
| `AWSSecretsAdapter` | Production (AWS) | AWS Secrets Manager |

### Selecting an Adapter

Set `SECRETS_ADAPTER` environment variable:

```bash
# Development (default)
export SECRETS_ADAPTER=dev

# HashiCorp Vault
export SECRETS_ADAPTER=vault
export VAULT_ADDR=https://vault.example.com:8200
export VAULT_TOKEN=s.xxxx

# AWS Secrets Manager
export SECRETS_ADAPTER=aws
export AWS_DEFAULT_REGION=us-east-1
```

---

## Migration Guide

### Migrating from `config/api_keys.json`

The legacy `config/api_keys.json` file stores API keys in plaintext. Follow these steps to migrate:

#### Step 1: Extract Current Secrets

```python
import json

with open("config/api_keys.json") as f:
    keys = json.load(f)

for key in keys["keys"]:
    print(f'{key["name"].upper()}_API_KEY={key["key"]}')
```

#### Step 2: Add to `.env` File

```bash
# .env
DEFAULT_DEVELOPMENT_KEY_API_KEY=5SKLBQk-eCZ3-...
TEST_USER_API_KEY=xt8vSinoueY8BLE1...
```

#### Step 3: Update Code to Use Adapter

Before:
```python
import json

with open("config/api_keys.json") as f:
    keys = json.load(f)
api_key = keys["keys"][0]["key"]
```

After:
```python
from security.secrets_adapter import get_secret

api_key = get_secret("DEFAULT_DEVELOPMENT_KEY_API_KEY")
```

#### Step 4: Remove Plaintext File

Once all callers are migrated and CI secret scanning is active:

```bash
git rm config/api_keys.json
git commit -m "Remove plaintext API keys - migrated to secrets adapter"
```

> [!CAUTION]
> After removing `api_keys.json`, **rotate all affected credentials** immediately. The old keys have been exposed in git history.

---

## Configuration Reference

### Secret References in Config Files

Use `secrets://` prefix in YAML/JSON config files:

```yaml
# config/database.yaml
database:
  host: localhost
  port: 5432
  username: app_user
  password: secrets://DB_PASSWORD  # Resolved at load time
  
redis:
  url: secrets://REDIS_URL
```

Load with secret resolution:

```python
from config.config_loader import load_config_with_secrets

config = load_config_with_secrets("config/database.yaml")
# config["database"]["password"] = actual password value
```

### Adapter Configuration

#### DevFileAdapter

```python
from security.secrets_adapter import DevFileAdapter

adapter = DevFileAdapter(
    env_path=".env.local",    # Custom .env path
    fallback_to_env=True      # Also check os.environ
)
```

#### VaultAdapter

```python
from security.secrets_adapter import VaultAdapter

adapter = VaultAdapter(
    url="https://vault.example.com:8200",
    token="s.xxxx",
    mount_point="secret",     # KV v2 mount point
    namespace="myns",         # Vault Enterprise namespace
    cache_ttl_seconds=300     # Cache duration
)
```

#### AWSSecretsAdapter

```python
from security.secrets_adapter import AWSSecretsAdapter

adapter = AWSSecretsAdapter(
    region="us-east-1",
    profile="production",     # AWS profile name
    cache_ttl_seconds=300
)
```

---

## Operational Runbooks

### Runbook: Rotate a Secret

#### For Development Secrets

1. Update the value in `.env`:
   ```bash
   # Generate new secret
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   
   # Update .env file
   API_KEY=NEW_VALUE_HERE
   ```

2. Restart the application.

#### For Vault Secrets

1. Write the new secret:
   ```bash
   vault kv put secret/myapp/api_key value="NEW_SECRET"
   ```

2. Clear application cache or restart:
   ```python
   from security.secrets_adapter import get_adapter
   adapter = get_adapter()
   adapter.clear_cache()  # VaultAdapter and AWSSecretsAdapter only
   ```

#### For AWS Secrets Manager

1. Update via AWS CLI:
   ```bash
   aws secretsmanager update-secret \
     --secret-id myapp/api_key \
     --secret-string '{"value": "NEW_SECRET"}'
   ```

2. Clear application cache or wait for TTL expiry.

---

### Runbook: Add a New Secret

1. **Development**: Add to `.env`:
   ```bash
   NEW_SECRET=value_here
   ```

2. **Production (Vault)**:
   ```bash
   vault kv put secret/myapp/new_secret value="production_value"
   ```

3. **Production (AWS)**:
   ```bash
   aws secretsmanager create-secret \
     --name myapp/new_secret \
     --secret-string '{"value": "production_value"}'
   ```

4. **Update configuration** (if using config files):
   ```yaml
   my_feature:
     api_key: secrets://NEW_SECRET
   ```

---

### Runbook: Debug Missing Secrets

1. **Check adapter type**:
   ```python
   from security.secrets_adapter import get_adapter
   adapter = get_adapter()
   print(f"Using: {adapter.__class__.__name__}")
   ```

2. **List available secrets**:
   ```python
   secrets = adapter.list_secrets("APP_")
   print(secrets)
   ```

3. **Check environment**:
   ```bash
   echo $SECRETS_ADAPTER
   echo $VAULT_ADDR  # if using Vault
   ```

---

## CI/CD Integration

### GitHub Actions Secret Injection

```yaml
# .github/workflows/deploy.yml
jobs:
  deploy:
    runs-on: ubuntu-latest
    env:
      SECRETS_ADAPTER: dev
    steps:
      - uses: actions/checkout@v4
      
      - name: Create .env from secrets
        run: |
          echo "API_KEY=${{ secrets.API_KEY }}" >> .env
          echo "JWT_SECRET=${{ secrets.JWT_SECRET }}" >> .env
          echo "DATABASE_URL=${{ secrets.DATABASE_URL }}" >> .env
      
      - name: Run tests
        run: python -m pytest
```

### Secret Scanning

The repository includes automatic secret scanning via `.github/workflows/secrets-scan.yml`:

- **Gitleaks**: Scans for hardcoded secrets
- **TruffleHog**: Verified secrets detection
- **detect-secrets**: Yelp's secret detection

> [!IMPORTANT]
> Never commit actual secrets. The CI workflow will fail if secrets are detected.

---

## Security Checklist

When modifying code that handles secrets:

- [ ] No secret values in code diffs
- [ ] Adapter code does not log secret values
- [ ] Tests use `DevFileAdapter` with test values or mocks
- [ ] Config examples use `secrets://` placeholders, not real values
- [ ] `.env` files are in `.gitignore`
- [ ] Secrets have appropriate TTL/expiration

---

## Troubleshooting

### "Secret not found" Error

1. Check if the secret exists in your `.env` or secret store
2. Verify `SECRETS_ADAPTER` is set correctly
3. Check for typos in secret name

### Vault Connection Issues

```python
from security.secrets_adapter import VaultAdapter

adapter = VaultAdapter()
print(adapter._client.is_authenticated())  # Should be True
```

### AWS Permissions

Ensure IAM role has `secretsmanager:GetSecretValue` permission:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": "secretsmanager:GetSecretValue",
    "Resource": "arn:aws:secretsmanager:*:*:secret:myapp/*"
  }]
}
```
