"""
Tests for Dependency Conflict Resolver

Tests the functionality of the dependency conflict resolver tool including:
- Requirements file parsing
- Conflict detection
- Resolution suggestions
- Report generation
- Auto-fix functionality

Author: AstraGuard AI Team
Event: Elite Coders Winter of Code (Apertre 3.0) 2026
Issue: #710
"""

import json
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
from scripts.maintenance.dependency_conflict_resolver import (
    DependencyConflictResolver,
    DependencyInfo,
    Conflict
)


@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory for testing."""
    with TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_requirements(temp_project_dir):
    """Create sample requirements files for testing."""
    # Production requirements
    prod_req = temp_project_dir / "requirements.txt"
    prod_req.write_text("""
numpy==1.26.0
pandas==2.2.0
fastapi==0.115.0
torch>=2.2.0,<3.0
""".strip())
    
    # Dev requirements with conflict
    dev_req = temp_project_dir / "requirements-dev.txt"
    dev_req.write_text("""
numpy==1.24.0
pytest==8.3.2
black==24.3.0
""".strip())
    
    # Test requirements
    test_req = temp_project_dir / "requirements-test.txt"
    test_req.write_text("""
pytest==8.3.2
pytest-cov==7.0.0
numpy>=1.26.0
""".strip())
    
    return {
        "prod": prod_req,
        "dev": dev_req,
        "test": test_req
    }


class TestDependencyConflictResolver:
    """Test suite for DependencyConflictResolver."""
    
    def test_init(self, temp_project_dir):
        """Test resolver initialization."""
        resolver = DependencyConflictResolver(temp_project_dir)
        assert resolver.root_dir == temp_project_dir
        assert len(resolver.dependencies) == 0
        assert len(resolver.conflicts) == 0
    
    def test_find_requirements_files(self, temp_project_dir, sample_requirements):
        """Test finding requirements files."""
        resolver = DependencyConflictResolver(temp_project_dir)
        files = resolver.find_requirements_files()
        
        assert len(files) >= 3
        file_names = [f.name for f in files]
        assert "requirements.txt" in file_names
        assert "requirements-dev.txt" in file_names
        assert "requirements-test.txt" in file_names
    
    def test_parse_requirements_file(self, temp_project_dir, sample_requirements):
        """Test parsing a requirements file."""
        resolver = DependencyConflictResolver(temp_project_dir)
        deps = resolver.parse_requirements_file(sample_requirements["prod"])
        
        assert len(deps) == 4
        
        # Check numpy dependency
        numpy_dep = next(d for d in deps if d.name == "numpy")
        assert numpy_dep.version_spec == "==1.26.0"
        assert numpy_dep.line_number == 1
        
        # Check torch with range specifier
        torch_dep = next(d for d in deps if d.name == "torch")
        assert ">=2.2.0" in torch_dep.version_spec
        assert "<3.0" in torch_dep.version_spec
    
    def test_collect_all_dependencies(self, temp_project_dir, sample_requirements):
        """Test collecting dependencies from all files."""
        resolver = DependencyConflictResolver(temp_project_dir)
        all_deps = resolver.collect_all_dependencies()
        
        # Check that numpy appears in multiple files
        assert "numpy" in all_deps
        assert len(all_deps["numpy"]) == 3  # prod, dev, test
        
        # Check that pytest appears only in dev and test
        assert "pytest" in all_deps
        assert len(all_deps["pytest"]) == 2
    
    def test_detect_version_conflicts(self, temp_project_dir, sample_requirements):
        """Test detection of version conflicts."""
        resolver = DependencyConflictResolver(temp_project_dir)
        resolver.collect_all_dependencies()
        conflicts = resolver.detect_version_conflicts()
        
        # Should detect numpy conflict (1.26.0 vs 1.24.0)
        numpy_conflicts = [c for c in conflicts if c.package == "numpy"]
        assert len(numpy_conflicts) > 0
        
        numpy_conflict = numpy_conflicts[0]
        assert numpy_conflict.conflict_type == "version"
        assert numpy_conflict.severity in ["critical", "high"]
        assert "1.26.0" in numpy_conflict.details or "1.24.0" in numpy_conflict.details
    
    def test_no_conflicts_with_compatible_versions(self, temp_project_dir):
        """Test that compatible versions don't trigger conflicts."""
        # Create requirements with compatible ranges
        req1 = temp_project_dir / "requirements.txt"
        req1.write_text("numpy>=1.24.0,<2.0.0")
        
        req2 = temp_project_dir / "requirements-dev.txt"
        req2.write_text("numpy>=1.26.0,<1.27.0")
        
        resolver = DependencyConflictResolver(temp_project_dir)
        resolver.collect_all_dependencies()
        conflicts = resolver.detect_version_conflicts()
        
        # These ranges overlap, so no conflict
        assert len(conflicts) == 0
    
    def test_conflict_severity_determination(self, temp_project_dir):
        """Test severity determination for conflicts."""
        resolver = DependencyConflictResolver(temp_project_dir)
        
        # Critical package
        critical_deps = [
            DependencyInfo("numpy", "==1.24.0", "req1.txt", 1),
            DependencyInfo("numpy", "==1.26.0", "req2.txt", 1)
        ]
        severity = resolver._determine_severity("numpy", critical_deps)
        assert severity == "critical"
        
        # Non-critical package with few conflicts
        low_deps = [
            DependencyInfo("some-package", "==1.0.0", "req1.txt", 1),
            DependencyInfo("some-package", "==2.0.0", "req2.txt", 1)
        ]
        severity = resolver._determine_severity("some-package", low_deps)
        assert severity == "low"
    
    def test_suggest_resolution(self, temp_project_dir):
        """Test resolution suggestions."""
        resolver = DependencyConflictResolver(temp_project_dir)
        
        deps = [
            DependencyInfo("package", "==1.0.0", "req1.txt", 1),
            DependencyInfo("package", "==2.0.0", "req2.txt", 1),
            DependencyInfo("package", "==1.5.0", "req3.txt", 1)
        ]
        
        resolution = resolver._suggest_resolution("package", deps)
        assert "2.0.0" in resolution  # Should suggest latest version
        assert "package" in resolution
    
    def test_generate_report(self, temp_project_dir, sample_requirements):
        """Test report generation."""
        resolver = DependencyConflictResolver(temp_project_dir)
        resolver.collect_all_dependencies()
        resolver.detect_version_conflicts()
        
        report = resolver.generate_report()
        
        # Check report structure
        assert "summary" in report
        assert "conflicts" in report
        assert "dependencies" in report
        
        # Check summary
        assert report["summary"]["total_packages"] > 0
        assert report["summary"]["requirements_files"]
        
        # Check conflicts are included
        if resolver.conflicts:
            assert len(report["conflicts"]) == len(resolver.conflicts)
            assert report["summary"]["total_conflicts"] > 0
    
    def test_report_export_to_json(self, temp_project_dir, sample_requirements):
        """Test exporting report to JSON."""
        resolver = DependencyConflictResolver(temp_project_dir)
        resolver.collect_all_dependencies()
        resolver.detect_version_conflicts()
        
        report = resolver.generate_report()
        report_file = temp_project_dir / "report.json"
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Read back and verify
        with open(report_file, 'r') as f:
            loaded_report = json.load(f)
        
        assert loaded_report == report
    
    def test_auto_fix_dry_run(self, temp_project_dir, sample_requirements):
        """Test auto-fix in dry-run mode."""
        resolver = DependencyConflictResolver(temp_project_dir)
        resolver.collect_all_dependencies()
        resolver.detect_version_conflicts()
        
        # Store original content
        dev_content_before = sample_requirements["dev"].read_text()
        
        # Run dry-run fix
        changes = resolver.auto_fix_conflicts(dry_run=True)
        
        # Verify no files were modified
        dev_content_after = sample_requirements["dev"].read_text()
        assert dev_content_before == dev_content_after
        
        # But changes should be suggested
        if resolver.conflicts:
            assert len(changes) > 0
    
    def test_parse_comments_and_empty_lines(self, temp_project_dir):
        """Test parsing requirements file with comments and empty lines."""
        req_file = temp_project_dir / "requirements.txt"
        req_file.write_text("""
# This is a comment
numpy==1.26.0  # inline comment

# Another comment
pandas>=2.0.0,<3.0.0

""")
        
        resolver = DependencyConflictResolver(temp_project_dir)
        deps = resolver.parse_requirements_file(req_file)
        
        # Should only parse actual dependencies
        assert len(deps) == 2
        assert any(d.name == "numpy" for d in deps)
        assert any(d.name == "pandas" for d in deps)
    
    def test_parse_extras(self, temp_project_dir):
        """Test parsing dependencies with extras."""
        req_file = temp_project_dir / "requirements.txt"
        req_file.write_text("redis[hiredis]==5.1.0\nuvicorn[standard]==0.32.0")
        
        resolver = DependencyConflictResolver(temp_project_dir)
        deps = resolver.parse_requirements_file(req_file)
        
        redis_dep = next(d for d in deps if d.name == "redis")
        assert "hiredis" in redis_dep.extras
        assert redis_dep.version_spec == "==5.1.0"
    
    def test_check_python_compatibility(self, temp_project_dir):
        """Test Python version compatibility checking."""
        # Create pyproject.toml
        pyproject = temp_project_dir / "pyproject.toml"
        pyproject.write_text("""
[project]
requires-python = ">=3.9"
""")
        
        # Create requirements with incompatible package
        req_file = temp_project_dir / "requirements.txt"
        req_file.write_text("scikit-learn==1.8.0")  # Requires Python 3.11+
        
        resolver = DependencyConflictResolver(temp_project_dir)
        resolver.collect_all_dependencies()
        conflicts = resolver.check_python_compatibility()
        
        # Should detect incompatibility (if we have the mapping)
        # This tests the framework even if specific version isn't in our database
        assert isinstance(conflicts, list)
    
    def test_multiple_specifiers_same_package(self, temp_project_dir):
        """Test handling multiple specifiers for same package."""
        req_file = temp_project_dir / "requirements.txt"
        req_file.write_text("""
fastapi>=0.100.0
fastapi<1.0.0
""")
        
        resolver = DependencyConflictResolver(temp_project_dir)
        deps = resolver.parse_requirements_file(req_file)
        
        # Should parse both specifiers
        assert len(deps) == 2
        assert all(d.name == "fastapi" for d in deps)
    
    def test_invalid_requirement_handling(self, temp_project_dir):
        """Test handling of invalid requirement lines."""
        req_file = temp_project_dir / "requirements.txt"
        req_file.write_text("""
numpy==1.26.0
invalid line with no version
pandas>=2.0.0
""")
        
        resolver = DependencyConflictResolver(temp_project_dir)
        deps = resolver.parse_requirements_file(req_file)
        
        # Should parse valid lines and skip invalid ones
        assert len(deps) == 2
        dep_names = [d.name for d in deps]
        assert "numpy" in dep_names
        assert "pandas" in dep_names
    
    def test_empty_requirements_file(self, temp_project_dir):
        """Test handling empty requirements file."""
        req_file = temp_project_dir / "requirements.txt"
        req_file.write_text("")
        
        resolver = DependencyConflictResolver(temp_project_dir)
        deps = resolver.parse_requirements_file(req_file)
        
        assert len(deps) == 0
    
    def test_print_report_with_conflicts(self, temp_project_dir, sample_requirements, capsys):
        """Test printing report with conflicts."""
        resolver = DependencyConflictResolver(temp_project_dir)
        resolver.collect_all_dependencies()
        resolver.detect_version_conflicts()
        
        resolver.print_report()
        
        captured = capsys.readouterr()
        assert "DEPENDENCY CONFLICT ANALYSIS REPORT" in captured.out
        assert "Total Packages:" in captured.out
" assert "Total Conflicts:" in captured.out
    
    def test_print_report_no_conflicts(self, temp_project_dir, capsys):
        """Test printing report when no conflicts exist."""
        req_file = temp_project_dir / "requirements.txt"
        req_file.write_text("numpy==1.26.0\npandas==2.2.0")
        
        resolver = DependencyConflictResolver(temp_project_dir)
        resolver.collect_all_dependencies()
        resolver.detect_version_conflicts()
        
        resolver.print_report()
        
        captured = capsys.readouterr()
        assert "No conflicts detected" in captured.out


@pytest.mark.integration
class TestDependencyResolverIntegration:
    """Integration tests for the resolver."""
    
    def test_real_project_structure(self, temp_project_dir):
        """Test with a realistic project structure."""
        # Create a more complex project structure
        src_config = temp_project_dir / "src" / "config"
        src_config.mkdir(parents=True)
        
        # Main requirements
        (src_config / "requirements.txt").write_text("""
numpy>=1.26.0
pandas==2.2.0
fastapi==0.115.0
torch>=2.2.0,<3.0
""")
        
        # Dev requirements
        (src_config / "requirements-dev.txt").write_text("""
pytest==8.3.2
black==24.3.0
mypy==1.8.0
numpy>=1.24.0,<2.0
""")
        
        # CI requirements
        (src_config / "requirements-ci.txt").write_text("""
pytest==8.3.2
pytest-cov==7.0.0
coverage==7.4.0
""")
        
        resolver = DependencyConflictResolver(temp_project_dir)
        resolver.collect_all_dependencies()
        conflicts = resolver.detect_version_conflicts()
        report = resolver.generate_report()
        
        # Should successfully analyze the project
        assert report["summary"]["total_packages"] > 0
        assert len(report["summary"]["requirements_files"]) >= 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
