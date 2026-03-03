# Test Data Seeding Utilities

Comprehensive test data seeding utilities for AstraGuard testing scenarios. Supports database seeding, in-memory stores, and scenario-based test data generation.

## Features

- **Database Seeding**: Seed SQLite databases with users, telemetry, submissions, and API keys
- **Memory Store Seeding**: Populate in-memory data structures (lists, dicts)
- **Scenario-Based Seeding**: Predefined scenarios (normal ops, stress test, anomaly detection)
- **Flexible Configuration**: Customize data generation parameters
- **Batch Operations**: Efficient bulk data insertion
- **Cleanup Utilities**: Easy data cleanup between tests
- **Quality Assurance**: Generated data validates against model constraints

## Installation

```python
from src.backend.utils import (
    DatabaseSeeder,
    MemoryStoreSeeder,
    ScenarioSeeder,
    SeedConfig,
    ScenarioType,
    quick_seed_db,
    quick_seed_telemetry,
    quick_seed_users,
)
```

## Usage Examples

### Database Seeding

```python
from src.backend.utils import DatabaseSeeder

# Using context manager (recommended)
with DatabaseSeeder("test.db") as seeder:
    # Seed users
    user_ids = seeder.seed_users(count=10)
    
    # Seed telemetry data
    telemetry_ids = seeder.seed_telemetry(
        count=100,
        anomalous_ratio=0.2,  # 20% anomalous readings
        time_range_hours=24
    )
    
    # Seed contact submissions
    submission_ids = seeder.seed_contact_submissions(
        count=20,
        status_distribution={"pending": 0.6, "resolved": 0.4}
    )
    
    # Seed API keys
    api_keys = seeder.seed_api_keys(count=5)

# Manual connection management
seeder = DatabaseSeeder("test.db")
seeder.connect()
seeder.seed_users(count=10)
seeder.close()
```

### Memory Store Seeding

```python
from src.backend.utils import MemoryStoreSeeder

# Seed telemetry into a list
telemetry_list = []
MemoryStoreSeeder.seed_telemetry_list(
    telemetry_list,
    count=100,
    anomalous_ratio=0.1,
    time_range_hours=24
)

# Seed users into a dictionary
users_dict = {}
MemoryStoreSeeder.seed_user_dict(
    users_dict,
    count=10,
    roles=["admin", "operator"]
)

print(len(telemetry_list))  # 100
print(len(users_dict))      # 10
```

### Scenario-Based Seeding

```python
from src.backend.utils import DatabaseSeeder, ScenarioSeeder, ScenarioType

with DatabaseSeeder("test.db") as seeder:
    # Seed predefined scenario
    ScenarioSeeder.seed_scenario(ScenarioType.NORMAL_OPS, seeder)

# Available scenarios:
# - NORMAL_OPS: Typical operational data (5 users, 100 telemetry, 3 API keys)
# - ANOMALY_DETECTION: High anomaly ratio for testing detection (30% anomalous)
# - STRESS_TEST: Large datasets (50 users, 10k telemetry, 500 submissions)
# - HIGH_LOAD: High volume telemetry (5k records)
# - FAILURE_RECOVERY: High failure rate scenarios (50% anomalous)
# - EMPTY: Clear all data from database
```

### Convenience Functions

```python
from src.backend.utils import (
    quick_seed_db,
    quick_seed_telemetry,
    quick_seed_users
)

# Quick database seeding
quick_seed_db("test.db", ScenarioType.NORMAL_OPS)

# Quick telemetry generation
telemetry = quick_seed_telemetry(count=50, anomalous=True)

# Quick user generation
users = quick_seed_users(count=10)
```

### Custom Configuration

```python
from src.backend.utils import SeedConfig, DatabaseSeeder

# Create custom configuration
config = SeedConfig(
    telemetry_count=500,
    user_count=20,
    api_key_count=10,
    anomaly_ratio=0.25,
    time_range_hours=48,
    batch_size=100,
    seed=42  # For reproducible randomness
)

with DatabaseSeeder("test.db") as seeder:
    ScenarioSeeder.seed_scenario(ScenarioType.STRESS_TEST, seeder, config)
```

### Data Cleanup

```python
from src.backend.utils import DatabaseSeeder

with DatabaseSeeder("test.db") as seeder:
    # Clear specific table
    seeder.clear_table("users")
    
    # Clear all tables (EMPTY scenario)
    ScenarioSeeder.seed_scenario(ScenarioType.EMPTY, seeder)
```

## API Reference

### DatabaseSeeder

Main class for seeding SQLite databases.

#### Methods

**`__init__(db_path: Union[str, Path])`**
- Initialize database seeder
- `db_path`: Path to SQLite database

**`connect()`**
- Open database connection
- Called automatically by context manager

**`close()`**
- Close database connection and commit changes
- Called automatically by context manager

**`seed_users(count: int = 10, roles: Optional[List[str]] = None, table_name: str = "users") -> List[int]`**
- Seed user records
- Returns: List of inserted user IDs

**`seed_telemetry(count: int = 100, anomalous_ratio: float = 0.1, time_range_hours: int = 24, table_name: str = "telemetry") -> List[int]`**
- Seed telemetry records
- Returns: List of inserted telemetry IDs

**`seed_contact_submissions(count: int = 20, status_distribution: Optional[Dict[str, float]] = None, table_name: str = "contact_submissions") -> List[int]`**
- Seed contact form submissions
- Returns: List of inserted submission IDs

**`seed_api_keys(count: int = 5, table_name: str = "api_keys") -> List[str]`**
- Seed API keys
- Returns: List of generated API keys

**`clear_table(table_name: str)`**
- Clear all records from a table

### MemoryStoreSeeder

Static methods for seeding in-memory data structures.

#### Methods

**`seed_telemetry_list(target_list: List, count: int = 100, anomalous_ratio: float = 0.1, time_range_hours: int = 24)`**
- Seed telemetry data into a list

**`seed_user_dict(target_dict: Dict, count: int = 10, roles: Optional[List[str]] = None)`**
- Seed user data into a dictionary (keyed by username)

### ScenarioSeeder

Seed data for specific test scenarios.

#### Methods

**`seed_scenario(scenario: ScenarioType, db_seeder: DatabaseSeeder, config: Optional[SeedConfig] = None)`**
- Seed data for a specific scenario
- `scenario`: Type of scenario to seed
- `db_seeder`: DatabaseSeeder instance
- `config`: Optional seed configuration

### ScenarioType (Enum)

Predefined seeding scenarios:

- **NORMAL_OPS**: Typical operational data
  - 5 users, 100 telemetry records, 3 API keys
  - 5% anomaly ratio
  - 24-hour time range

- **ANOMALY_DETECTION**: High anomaly ratio for testing
  - 3 users, 200 telemetry records
  - 30% anomaly ratio
  - 12-hour time range

- **STRESS_TEST**: Large datasets for load testing
  - 50 users, 10,000 telemetry records
  - 20 API keys, 500 contact submissions
  - 168-hour time range (1 week)

- **HIGH_LOAD**: High volume telemetry
  - 5,000 telemetry records, 200 submissions
  - 48-hour time range

- **FAILURE_RECOVERY**: High failure rate scenarios
  - 10 users, 500 telemetry records
  - 50% anomaly ratio
  - 12-hour time range

- **EMPTY**: Clear all data from database

### SeedConfig

Configuration for data seeding.

#### Attributes

- `telemetry_count: int = 100` - Number of telemetry records
- `user_count: int = 10` - Number of users
- `api_key_count: int = 5` - Number of API keys
- `anomaly_ratio: float = 0.1` - Ratio of anomalous records (0.0 to 1.0)
- `time_range_hours: int = 24` - Time range for timestamps
- `batch_size: int = 50` - Batch size for insertions
- `seed: Optional[int] = None` - Random seed for reproducibility

### Convenience Functions

**`quick_seed_db(db_path, scenario, config=None)`**
- Quick function to seed a database with a scenario

**`quick_seed_telemetry(count=100, anomalous=False) -> List[Dict]`**
- Quick function to generate telemetry data

**`quick_seed_users(count=10) -> Dict[str, Dict]`**
- Quick function to generate user data

## Pytest Integration

### Using Seeders in Test Fixtures

```python
import pytest
from src.backend.utils import DatabaseSeeder, ScenarioType

@pytest.fixture
def seeded_db(tmp_path):
    """Provide a pre-seeded database for tests."""
    db_path = tmp_path / "test.db"
    
    # Create tables
    conn = sqlite3.connect(db_path)
    # ... create tables ...
    conn.close()
    
    # Seed data
    with DatabaseSeeder(db_path) as seeder:
        ScenarioSeeder.seed_scenario(ScenarioType.NORMAL_OPS, seeder)
    
    yield db_path


def test_with_seeded_data(seeded_db):
    """Test using pre-seeded database."""
    conn = sqlite3.connect(seeded_db)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM users")
    assert cursor.fetchone()[0] > 0
    
    conn.close()
```

### Seeding for Specific Tests

```python
def test_anomaly_detection(test_db):
    """Test anomaly detection with seeded anomalous data."""
    with DatabaseSeeder(test_db) as seeder:
        seeder.seed_telemetry(count=100, anomalous_ratio=0.5)
    
    # Run anomaly detection tests
    # ...
```

## Performance Considerations

### Batch Operations

The seeder uses efficient batch operations for large datasets:

```python
with DatabaseSeeder("test.db") as seeder:
    # This efficiently inserts 10,000 records
    seeder.seed_telemetry(count=10000)
```

### Memory Usage

For very large datasets, the seeder streams data to avoid memory issues:

```python
# Seed 100k records without excessive memory usage
seeder.seed_telemetry(count=100000)
```

### Timing

Approximate seeding times on standard hardware:
- **100 users**: ~10ms
- **1,000 telemetry records**: ~50ms
- **10,000 telemetry records**: ~500ms
- **100,000 telemetry records**: ~5s

## Data Quality

Seeded data meets the following quality criteria:

### Telemetry
- Timestamps are sequential and ordered
- Normal values within operational ranges (voltage 7-9V, temp 20-50°C)
- Anomalous values outside normal ranges
- All required fields populated

### Users
- Unique usernames and emails
- Valid email format
- Timestamps in the past
- Consistent role assignments

### API Keys
- 32-character alphanumeric keys
- Unique keys
- Valid permission sets
- Realistic usage counts

### Contact Submissions
- Realistic names and emails
- Valid phone numbers
- IP addresses in private ranges
- Proper status distribution

## Integration Examples

### E2E Testing

```python
@pytest.fixture(scope="module")
def e2e_database():
    """Set up database for end-to-end testing."""
    db_path = "e2e_test.db"
    
    # Create schema
    init_database(db_path)
    
    # Seed comprehensive test data
    with DatabaseSeeder(db_path) as seeder:
        seeder.seed_users(count=20, roles=["admin", "operator", "viewer"])
        seeder.seed_telemetry(count=1000, anomalous_ratio=0.1)
        seeder.seed_api_keys(count=10)
        seeder.seed_contact_submissions(count=50)
    
    yield db_path
    
    # Cleanup
    Path(db_path).unlink()
```

### Load Testing

```python
def setup_load_test_data():
    """Prepare database for load testing."""
    with DatabaseSeeder("load_test.db") as seeder:
        ScenarioSeeder.seed_scenario(ScenarioType.STRESS_TEST, seeder)
        
        # Additional custom data
        seeder.seed_telemetry(count=50000, anomalous_ratio=0.05)
```

### Development Environment

```python
def seed_dev_database():
    """Seed development database with realistic data."""
    config = SeedConfig(
        telemetry_count=10000,
        user_count=50,
        api_key_count=20,
        anomaly_ratio=0.08,
        time_range_hours=168,  # 1 week
        seed=42  # Reproducible
    )
    
    quick_seed_db("dev.db", ScenarioType.NORMAL_OPS, config)
```

## Best Practices

1. **Use Context Managers**: Always use `with DatabaseSeeder()` for automatic cleanup

2. **Clear Between Tests**: Use `clear_table()` or `EMPTY` scenario to ensure test isolation

3. **Reproducible Tests**: Set `seed` in `SeedConfig` for reproducible random data

4. **Appropriate Scenarios**: Choose the right scenario for your test type

5. **Validate Seeded Data**: Always verify seeded data meets test requirements

6. **Cleanup After Tests**: Remove temporary databases in `teardown` or `finally` blocks

## Testing

Run the test suite:

```bash
pytest tests/utils/test_seeders.py -v
```

The test suite includes:
- Configuration validation (3 tests)
- Database seeding operations (10 tests)
- Memory store seeding (4 tests)
- Scenario seeding (4 tests)
- Convenience functions (4 tests)
- Data quality validation (4 tests)
- Edge cases (3 tests)

**Total: 32 tests, all passing**

## Troubleshooting

### SQLite Constraints

If you encounter unique constraint errors:

```python
# Clear existing data first
seeder.clear_table("users")
seeder.seed_users(count=10)
```

### Table Not Found

Ensure tables exist before seeding:

```python
# Create schema first
init_database(db_path)

# Then seed
with DatabaseSeeder(db_path) as seeder:
    seeder.seed_users(count=10)
```

### Memory Issues

For very large datasets, seed in batches:

```python
# Instead of seeding 100k at once
for _ in range(10):
    seeder.seed_telemetry(count=10000)
```

## License

Part of the AstraGuard AI Apertre 3.0 project.
