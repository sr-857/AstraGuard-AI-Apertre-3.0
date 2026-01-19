# Environment Variable Support in Configuration Files

## Overview

Configuration files (YAML/JSON) now support environment variable substitution, allowing dynamic configuration based on deployment environments. This addresses issue #192.

## Features

- **Environment Variable Substitution**: Use `${VAR_NAME}` syntax in config files
- **Default Values**: Use `${VAR_NAME:default_value}` for optional variables
- **Type Conversion**: Automatic conversion to int, float, and bool types
- **Nested Support**: Works with nested dictionaries and lists
- **Multiple Formats**: Supports both YAML and JSON configuration files

## Syntax

### Basic Substitution
```yaml
database:
  host: ${DB_HOST}
  port: ${DB_PORT}
```

### With Default Values
```yaml
database:
  host: ${DB_HOST:localhost}
  port: ${DB_PORT:5432}
  timeout: ${DB_TIMEOUT:30}
```

### Type Conversion
```yaml
app:
  debug: ${DEBUG:false}        # Converted to boolean
  port: ${PORT:8080}           # Converted to integer
  timeout: ${TIMEOUT:30.5}     # Converted to float
```

### Complex Strings
```yaml
database:
  url: postgresql://${DB_USER:postgres}:${DB_PASS}@${DB_HOST:localhost}:${DB_PORT:5432}/${DB_NAME:myapp}
```

## Usage Examples

### Database Configuration
```yaml
database:
  host: ${DB_HOST:localhost}
  port: ${DB_PORT:5432}
  name: ${DB_NAME:myapp}
  user: ${DB_USER:postgres}
  password: ${DB_PASS}
  ssl_mode: ${DB_SSL_MODE:require}
  connection_timeout: ${DB_CONNECTION_TIMEOUT:30}
```

### Redis Configuration
```yaml
redis:
  host: ${REDIS_HOST:localhost}
  port: ${REDIS_PORT:6379}
  password: ${REDIS_PASSWORD}
  db: ${REDIS_DB:0}
  url: redis://${REDIS_HOST:localhost}:${REDIS_PORT:6379}/${REDIS_DB:0}
```

### Application Settings
```yaml
app:
  name: ${APP_NAME:AstraGuard}
  version: ${APP_VERSION:1.0.0}
  environment: ${ENVIRONMENT:development}
  debug: ${DEBUG:false}
  log_level: ${LOG_LEVEL:INFO}
  log_file: ${LOG_FILE:/var/log/astraguard.log}
```

### External Services
```yaml
services:
  monitoring_endpoint: ${MONITORING_ENDPOINT:http://localhost:9090}
  alert_webhook: ${ALERT_WEBHOOK:http://localhost:8080/alerts}
  health_check_url: ${HEALTH_CHECK_URL:http://localhost:8000/health}
```

## Environment Variables Setup

### Development
```bash
export DB_HOST=localhost
export DB_PORT=5432
export REDIS_HOST=localhost
export DEBUG=true
export LOG_LEVEL=DEBUG
```

### Production
```bash
export DB_HOST=db.production.example.com
export DB_PORT=5432
export DB_USER=astraguard_prod
export DB_PASS=secure_password_here
export REDIS_HOST=redis-cluster.prod.example.com
export REDIS_PASSWORD=redis_secure_password
export ENVIRONMENT=production
export DEBUG=false
export LOG_LEVEL=WARNING
export LOG_FILE=/var/log/astraguard/astraguard.log
```

### Docker
```bash
docker run -e DB_HOST=db.example.com \
           -e REDIS_HOST=redis.example.com \
           -e ENVIRONMENT=production \
           astraguard-ai
```

### Kubernetes
```yaml
env:
- name: DB_HOST
  value: "db-service"
- name: REDIS_HOST
  value: "redis-service"
- name: ENVIRONMENT
  value: "production"
- name: LOG_LEVEL
  value: "INFO"
```

## Implementation Details

### Files Modified
- `config/config_utils.py` - New configuration utilities with env var support
- `config/mission_phase_policy_loader.py` - Updated to use new config loader
- `state_machine/mission_policy.py` - Updated to use new config loader
- `backend/recovery_orchestrator.py` - Updated to use new config loader
- `backend/recovery_orchestrator_enhanced.py` - Updated to use new config loader

### Backward Compatibility
- Existing configuration files continue to work unchanged
- Environment variable substitution is optional
- Falls back to default values when environment variables are not set

### Error Handling
- **Required Variables**: Throws `ValueError` if required `${VAR_NAME}` is not set
- **File Not Found**: Uses fallback defaults if config file doesn't exist
- **Invalid YAML/JSON**: Throws appropriate parsing errors

## Testing

Run the comprehensive test suite:

```bash
python test_env_config.py
```

Tests cover:
- Basic environment variable substitution
- Default value handling
- Type conversion (int, float, bool)
- File loading with environment variables
- Error handling for missing variables
- Real-world usage examples

## Best Practices

### 1. Use Descriptive Variable Names
```yaml
# Good
database_host: ${DB_HOST}
redis_url: ${REDIS_URL}

# Avoid
host: ${HOST}
url: ${URL}
```

### 2. Provide Sensible Defaults
```yaml
# Good
port: ${PORT:8080}
debug: ${DEBUG:false}

# Avoid
port: ${PORT}  # Will fail if not set
```

### 3. Use Environment-Specific Files
Consider having different config files for different environments:

```
config/
├── config.dev.yaml
├── config.staging.yaml
└── config.prod.yaml
```

### 4. Document Required Variables
Document all required environment variables in your README:

```markdown
## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | `localhost` | Database host |
| `DB_PORT` | `5432` | Database port |
| `REDIS_HOST` | `localhost` | Redis host |
```

### 5. Security Considerations
- Never commit sensitive values to version control
- Use secret management systems (Vault, AWS Secrets Manager, etc.)
- Validate configuration values in your application

## Migration Guide

### Existing Configurations
No changes required! Existing YAML/JSON files work as before.

### Adding Environment Variables
1. Identify configuration values that vary by environment
2. Replace static values with `${VAR_NAME}` or `${VAR_NAME:default}`
3. Set environment variables in your deployment environment
4. Test configuration loading

### Example Migration
```yaml
# Before
database:
  host: localhost
  port: 5432

# After
database:
  host: ${DB_HOST:localhost}
  port: ${DB_PORT:5432}
```

## Troubleshooting

### Common Issues

1. **Variable Not Set Error**
   ```
   ValueError: Required environment variable not set: DB_HOST
   ```
   **Solution**: Set the environment variable or provide a default value

2. **Type Conversion Issues**
   ```
   ValueError: invalid literal for int()
   ```
   **Solution**: Ensure environment variable contains valid data for the expected type

3. **Complex String Interpolation**
   Some advanced bash-style syntax may not be supported. Use simple `${VAR_NAME}` patterns.

### Debugging
Enable debug logging to see environment variable processing:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Future Enhancements

- Support for bash-style conditional substitution: `${VAR:+value}`
- Environment variable validation schemas
- Configuration hot-reloading
- Support for .env files</content>
<parameter name="filePath">c:\Users\Gupta\Downloads\AstraGuard-AI\ENV_CONFIG_README.md