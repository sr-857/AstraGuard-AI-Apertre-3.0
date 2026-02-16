# Zero-Downtime Database Migration System

## Overview

AstraGuard AI implements a comprehensive zero-downtime database migration system that enables schema changes without service interruption. The system uses a dual-write pattern to ensure data consistency and provides automatic rollback capabilities.

## Architecture

### Core Components

1. **MigrationManager** - Coordinates the entire migration process
2. **DualWriteManager** - Manages simultaneous writes to old and new schemas
3. **VersionManager** - Tracks schema versions and migration history
4. **MigrationValidator** - Validates data integrity and performance
5. **RollbackManager** - Handles automatic and manual rollbacks
6. **MigrationMonitor** - Real-time monitoring of migration health

### Migration Strategies

- **DIRECT**: Traditional migration with brief downtime
- **DUAL_WRITE**: Zero-downtime with simultaneous writes (recommended)
- **BLUE_GREEN**: Blue-green deployment pattern
- **CANARY**: Canary release pattern

## Usage

### Basic Migration

```python
from data.migrations import MigrationManager, Migration, MigrationConfig, MigrationStrategy

# Configure migration
config = MigrationConfig(
    strategy=MigrationStrategy.DUAL_WRITE,
    auto_rollback_on_failure=True,
    performance_threshold_percent=5.0,
)

# Initialize manager
manager = MigrationManager("astraguard.db", config)
await manager.initialize()

# Define migration
class AddTelemetryColumns(Migration):
    @property
    def version(self) -> str:
        return "1.1.0"
    
    @property
    def name(self) -> str:
        return "add_telemetry_columns"
    
    @property
    def description(self) -> str:
        return "Add new telemetry columns"
    
    async def apply(self, db):
        await db.execute("ALTER TABLE telemetry ADD COLUMN cpu_usage REAL")
        await db.commit()
    
    async def revert(self, db):
        # Revert logic here
        pass

# Execute migration
result = await manager.migrate(AddTelemetryColumns())
print(f"Migration successful: {result.success}")
print(f"Duration: {result.duration_ms}ms")
```

### Dual-Write Pattern

```python
from data.migrations import DualWriteManager, ReadRoutingStrategy, WriteStrategy

# Create adapters for old and new schemas
old_adapter = SQLiteSchemaAdapter("old.db", "v1.0")
new_adapter = SQLiteSchemaAdapter("new.db", "v1.1")

# Configure dual-write
dual_write = DualWriteManager(
    old_adapter=old_adapter,
    new_adapter=new_adapter,
    read_strategy=ReadRoutingStrategy.DUAL_READ,
    write_strategy=WriteStrategy.DUAL_WRITE,
    consistency_check_interval=100,
)

# Write data (goes to both schemas)
result = await dual_write.write("key", "value")

# Read data (with routing strategy)
value = await dual_write.read("key")

# Gradually shift traffic
dual_write.shift_traffic(percentage_increase=10.0)
```

### Rollback

```python
from data.migrations import RollbackStrategy

# Automatic rollback on failure (enabled by default)
config = MigrationConfig(auto_rollback_on_failure=True)

# Manual rollback
result = await manager.rollback(
    to_version="1.0.0",
    strategy=RollbackStrategy.GRACEFUL,
    preserve_new_data=True,
)

print(f"Rollback successful: {result.success}")
print(f"Data preserved: {result.data_preserved}")
```

### Monitoring

```python
from data.migrations import MigrationMonitor, MetricType

# Create monitor
monitor = MigrationMonitor(
    migration_version="1.1.0",
    alert_callbacks=[lambda alert: print(f"ALERT: {alert}")],
)

# Start monitoring
monitor.start_monitoring()

# Record metrics
monitor.record_metric(MetricType.PERFORMANCE, 2.5, "percent")
monitor.record_operation(duration_ms=50, success=True)

# Check health
if not monitor.is_healthy():
    print("Migration has issues!")

# Generate report
report = monitor.generate_report()
print(json.dumps(report, indent=2))
```

## Configuration

### MigrationConfig Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `strategy` | MigrationStrategy | DUAL_WRITE | Migration execution strategy |
| `auto_rollback_on_failure` | bool | True | Automatically rollback on failure |
| `performance_threshold_percent` | float | 5.0 | Max acceptable performance impact |
| `consistency_check_interval` | int | 100 | Check consistency every N writes |
| `gradual_shift_increment` | float | 10.0 | Traffic shift percentage increment |
| `max_dual_write_duration_minutes` | int | 60 | Max dual-write phase duration |
| `preserve_data_on_rollback` | bool | True | Preserve data during rollback |

## Testing

### Run Migration Tests

```bash
# Run all migration tests
pytest tests/migrations/ -v

# Run specific test file
pytest tests/migrations/test_dual_write.py -v

# Run with benchmark markers
pytest tests/migrations/ -m benchmark -v
```

### Chaos Engineering

```bash
# Run migration chaos experiment
python -m chaos run src/chaos/experiments/migration_failure.yaml
```

## Best Practices

1. **Always use DUAL_WRITE strategy** for production migrations
2. **Set appropriate performance thresholds** (default 5%)
3. **Test migrations in staging** before production
4. **Monitor migration health** continuously
5. **Keep snapshots** for rollback capability
6. **Validate data integrity** after migration
7. **Use gradual traffic shifting** to minimize risk

## Acceptance Criteria

- ✅ Zero downtime migrations via dual-write pattern
- ✅ Automatic rollback on failure
- ✅ Data integrity maintained (100% checksum validation)
- ✅ Performance impact < 5%
- ✅ Migration tested in staging (chaos experiments)
- ✅ Backward-compatible schema changes
- ✅ Comprehensive monitoring and alerting

## Troubleshooting

### Migration Fails to Start

- Check database accessibility
- Verify version is not already applied
- Ensure sufficient disk space for snapshots

### Dual-Write Issues

- Check both schemas are healthy
- Verify consistency check interval
- Monitor for data inconsistencies

### Rollback Failures

- Verify snapshot exists for target version
- Check disk space for rollback operations
- Review rollback history for patterns

## API Reference

See `src/data/migrations/__init__.py` for complete API exports.
