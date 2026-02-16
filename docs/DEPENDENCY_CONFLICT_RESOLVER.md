# Dependency Conflict Resolver

## 📋 Overview

The Dependency Conflict Resolver is a comprehensive tool designed to detect and resolve dependency conflicts across multiple requirements files in the AstraGuard AI project. It helps maintain consistent dependency versions across production, development, testing, and CI environments.

## 🎯 Features

- **🔍 Conflict Detection**: Automatically detects version conflicts between requirements files
- **🐍 Python Compatibility**: Checks if dependencies are compatible with required Python version  
- **📊 Detailed Reports**: Generates comprehensive conflict reports with severity levels
- **🔧 Auto-Fix**: Automatically resolves conflicts where possible
- **💾 Export**: Export reports to JSON for further analysis
- **📝 Clear Documentation**: Provides suggested resolutions for each conflict

## 🚀 Quick Start

### Basic Analysis

```bash
python scripts/maintenance/dependency_conflict_resolver.py
```

This will:
1. Scan all `requirements*.txt` files in the project
2. Detect version conflicts
3. Check Python compatibility
4. Display a detailed report

### Auto-Fix Conflicts (Dry Run)

```bash
python scripts/maintenance/dependency_conflict_resolver.py --fix --dry-run
```

See what changes would be made without applying them.

### Auto-Fix Conflicts

```bash
python scripts/maintenance/dependency_conflict_resolver.py --fix
```

Automatically resolve conflicts by standardizing to compatible versions.

### Export Report

```bash
python scripts/maintenance/dependency_conflict_resolver.py --report conflicts.json
```

Export detailed conflict report to a JSON file for analysis or CI/CD integration.

## 📖 Usage Examples

### Example 1: Analyze Specific Directory

```bash
python scripts/maintenance/dependency_conflict_resolver.py --root /path/to/project
```

### Example 2: Fix and Export Report

```bash
python scripts/maintenance/dependency_conflict_resolver.py --fix --report report.json
```

### Example 3: CI/CD Integration

```bash
# In your CI pipeline
python scripts/maintenance/dependency_conflict_resolver.py --report conflicts.json
if [ $? -ne 0 ]; then
  echo "Dependency conflicts detected!"
  cat conflicts.json
  exit 1
fi
```

## 🔍 How It Works

### 1. **File Discovery**

The tool automatically finds all requirements files:
- `requirements.txt`
- `requirements-*.txt` (e.g., `requirements-dev.txt`, `requirements-test.txt`)
- Searches recursively in subdirectories

### 2. **Dependency Parsing**

Parses each requirements file and extracts:
- Package names
- Version specifiers (`==`, `>=`, `<=`, `~=`, etc.)
- Extras (e.g., `redis[hiredis]`)
- Source file and line number

Supports:
- Exact versions: `numpy==1.26.0`
- Range specifiers: `torch>=2.2.0,<3.0`
- Compatible releases: `fastapi~=0.115.0`
- Extras: `uvicorn[standard]==0.32.0`

### 3. **Conflict Detection**

Detects three types of conflicts:

#### Version Conflicts
When the same package appears with incompatible versions:

```
# requirements.txt
numpy==1.26.0

# requirements-dev.txt
numpy==1.24.0
```

#### Range Incompatibilities
When version ranges don't overlap:

```
# requirements.txt
fastapi>=0.115.0,<1.0.0

# requirements-dev.txt
fastapi>=1.0.0,<2.0.0
```

#### Python Incompatibility
When package versions require newer Python than specified:

```
# pyproject.toml
requires-python = ">=3.9"

# requirements.txt
scikit-learn==1.8.0  # Requires Python 3.11+
```

### 4. **Severity Assessment**

Each conflict is assigned a severity level:

| Severity | Description | Examples |
|----------|-------------|----------|
| **Critical** | Core dependencies that break functionality | `numpy`, `pandas`, `torch`, `fastapi` |
| **High** | Important dependencies affecting features | `scikit-learn`, `aiohttp`, `uvicorn` |
| **Medium** | Multiple conflicts or moderate impact | Packages with 3+ conflicts |
| **Low** | Minor dependencies with limited impact | Utility libraries |

### 5. **Resolution Suggestions**

For each conflict, the tool suggests:
- **Standardize to latest**: Use the highest compatible version
- **Consolidate ranges**: Merge overlapping ranges
- **Downgrade/upgrade**: Specific version recommendations
- **Remove duplicates**: Eliminate redundant specifications

### 6. **Auto-Fix**

The auto-fix feature:
1. Identifies resolvable conflicts
2. Selects the latest compatible version
3. Updates all affected requirements files
4. Preserves file formatting and comments

## 📊 Report Structure

### Console Report

```
================================================================================
🔍 DEPENDENCY CONFLICT ANALYSIS REPORT
================================================================================

📁 Requirements Files Analyzed: 4
   • src/config/requirements.txt
   • src/config/requirements-dev.txt
   • src/config/requirements-test.txt
   • src/config/requirements-ci.txt

📦 Total Packages: 45
⚠️  Total Conflicts: 2

🔴 CRITICAL SEVERITY (1 conflicts)
--------------------------------------------------------------------------------

1. Package: numpy
   Type: version
   Details: Incompatible version specifiers:
      • ==1.26.0 (from src/config/requirements.txt:1)
      • ==1.24.0 (from src/config/requirements-dev.txt:1)
   
   Conflicting Dependencies:
      • numpy==1.26.0
        from src/config/requirements.txt:1
      • numpy==1.24.0
        from src/config/requirements-dev.txt:4
   
   💡 Suggested Resolution:
      Use numpy==1.26.0 across all requirements files
```

### JSON Report

```json
{
  "summary": {
    "total_packages": 45,
    "total_conflicts": 2,
    "critical_conflicts": 1,
    "high_conflicts": 0,
    "medium_conflicts": 1,
    "low_conflicts": 0,
    "requirements_files": [
      "src/config/requirements.txt",
      "src/config/requirements-dev.txt"
    ]
  },
  "conflicts": [
    {
      "package": "numpy",
      "type": "version",
      "severity": "critical",
      "details": "Incompatible version specifiers...",
      "suggested_resolution": "Use numpy==1.26.0 across all files",
      "affected_files": [
        {
          "file": "src/config/requirements.txt",
          "line": 1,
          "version_spec": "==1.26.0"
        },
        {
          "file": "src/config/requirements-dev.txt",
          "line": 4,
          "version_spec": "==1.24.0"
        }
      ]
    }
  ],
  "dependencies": {
    "numpy": [
      {
        "version_spec": "==1.26.0",
        "source": "src/config/requirements.txt",
        "line": 1
      },
      {
        "version_spec": "==1.24.0",
        "source": "src/config/requirements-dev.txt",
        "line": 4
      }
    ]
  }
}
```

## 🎯 Common Use Cases

### Use Case 1: Pre-Commit Check

Add to `.git/hooks/pre-commit`:

```bash
#!/bin/bash
python scripts/maintenance/dependency_conflict_resolver.py
if [ $? -ne 0 ]; then
  echo "❌ Dependency conflicts detected! Please resolve before committing."
  exit 1
fi
```

### Use Case 2: CI/CD Pipeline

Add to `.github/workflows/dependencies.yml`:

```yaml
name: Dependency Check
on: [push, pull_request]

jobs:
  check-dependencies:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: pip install packaging
      - name: Check for conflicts
        run: python scripts/maintenance/dependency_conflict_resolver.py
```

### Use Case 3: Periodic Maintenance

Schedule weekly checks:

```bash
# In cron or scheduler
0 9 * * 1 cd /path/to/project && python scripts/maintenance/dependency_conflict_resolver.py --report weekly-report.json
```

## ⚙️ Configuration

The tool automatically adapts to project structure. No configuration required!

### Supported File Patterns

- `requirements.txt`
- `requirements-dev.txt`
- `requirements-test.txt`
- `requirements-ci.txt`
- Any file matching `requirements-*.txt`
- Recursively searches subdirectories

### Python Version Detection

Reads from `pyproject.toml`:

```toml
[project]
requires-python = ">=3.9"
```

Or `setup.py`:

```python
setup(
    python_requires=">=3.9",
)
```

## 🔧 Troubleshooting

### Issue: Tool doesn't find requirements files

**Solution**: Ensure files are named `requirements.txt` or `requirements-*.txt`

### Issue: False positive conflicts

**Explanation**: The tool is conservative and may flag packages that are technically compatible but use different version specifications.

**Solution**: Review the suggestions and use `--fix` to standardize to a single specification.

### Issue: Auto-fix doesn't work

**Causes**:
- File permissions
- Invalid file format
- Complex version constraints

**Solution**: Check file permissions and manually review suggested changes.

## 📚 API Reference

### Class: `DependencyConflictResolver`

Main class for resolving dependency conflicts.

#### Methods

##### `__init__(root_dir: Path = None)`

Initialize resolver with project root directory.

##### `find_requirements_files() -> List[Path]`

Find all requirements files in the project.

**Returns**: List of Path objects

##### `parse_requirements_file(file_path: Path) -> List[DependencyInfo]`

Parse a single requirements file.

**Args**:
- `file_path`: Path to requirements file

**Returns**: List of DependencyInfo objects

##### `collect_all_dependencies() -> Dict[str, List[DependencyInfo]]`

Collect dependencies from all requirements files.

**Returns**: Dictionary mapping package names to dependency info

##### `detect_version_conflicts() -> List[Conflict]`

Detect version conflicts between dependencies.

**Returns**: List of Conflict objects

##### `check_python_compatibility() -> List[Conflict]`

Check if dependencies are compatible with Python version.

**Returns**: List of Conflict objects

##### `generate_report() -> Dict`

Generate comprehensive conflict report.

**Returns**: Report dictionary

##### `print_report()`

Print human-readable report to console.

##### `auto_fix_conflicts(dry_run: bool = True) -> List[str]`

Auto-fix conflicts where possible.

**Args**:
- `dry_run`: If True, only show proposed changes

**Returns**: List of changes made/proposed

### Data Classes

#### `DependencyInfo`

```python
@dataclass
class DependencyInfo:
    name: str                  # Package name
    version_spec: str          # Version specifier
    source_file: str           # Source requirements file
    line_number: int           # Line number in file
    extras: List[str] = None   # Package extras
```

#### `Conflict`

```python
@dataclass
class Conflict:
    package: str               # Package name
    conflicts: List[DependencyInfo]  # Conflicting dependencies
    conflict_type: str         # "version", "missing", "incompatible"
    severity: str              # "critical", "high", "medium", "low"
    suggested_resolution: str  # Resolution suggestion
    details: str               # Detailed conflict description
```

## 🧪 Testing

Run the test suite:

```bash
# Run all tests
pytest tests/test_dependency_conflict_resolver.py -v

# Run specific test
pytest tests/test_dependency_conflict_resolver.py::TestDependencyConflictResolver::test_detect_version_conflicts -v

# Run with coverage
pytest tests/test_dependency_conflict_resolver.py --cov=scripts.maintenance.dependency_conflict_resolver --cov-report=html
```

## 🤝 Contributing

Contributions welcome! To add features:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## 📝 Best Practices

1. **Run regularly**: Check for conflicts before major releases
2. **Use in CI/CD**: Automate conflict detection in pipelines
3. **Review suggestions**: Always review auto-fix suggestions
4. **Keep consistent**: Maintain consistent versions across environments
5. **Document exceptions**: If you need different versions, document why

## 📄 License

MIT License - Part of AstraGuard AI project

## 🎯 Related Tools

- `pip-compile`: Generates locked requirements
- `pip-audit`: Security vulnerability scanning
- `safety`: Python dependency security checker
- `pipenv`: Python dependency management

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/sr-857/AstraGuard-AI-Apertre-3.0/issues)
- **Event**: Elite Coders Winter of Code (Apertre 3.0) 2026
- **Issue**: #710

---

**Last Updated**: February 15, 2026  
**Author**: AstraGuard AI Team  
**Version**: 1.0.0
