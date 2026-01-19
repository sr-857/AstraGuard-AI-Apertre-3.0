# Secrets Management Implementation TODO

## Core Secrets Module
- [ ] Create `core/secrets.py` with Fernet encryption
- [ ] Implement encrypted storage and on-demand decryption
- [ ] Add secret rotation with automatic key updates
- [ ] Integrate external secret managers (Vault, AWS)
- [ ] Add secure initialization scripts
- [ ] Implement validation to prevent secrets in logs/errors
- [ ] Add secret versioning for rollback
- [ ] Create health checks for secret accessibility

## CLI Commands
- [ ] Update `cli.py` with secret management commands (add, rotate, list)

## Testing
- [ ] Create `tests/test_secrets.py` with comprehensive tests
- [ ] Test encryption/decryption operations
- [ ] Test secret rotation functionality
- [ ] Test external manager integration
- [ ] Test security properties (no leaks in logs)

## Integration
- [ ] Update imports in `core/auth.py` to use secrets.py
- [ ] Update other files using secrets to use secrets.py
- [ ] Create .env.local from .env.template
- [ ] Verify no secrets exposed in logs
