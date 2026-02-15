#!/usr/bin/env python3
"""
Dependency Conflict Resolver for AstraGuard AI

This tool detects and resolves dependency conflicts across multiple
requirements files, ensuring compatibility and consistency.

Features:
- Parse multiple requirements files
- Detect version conflicts
- Check Python version compatibility
- Suggest resolution strategies
- Generate detailed conflict reports
- Auto-fix conflicts (optional)

Usage:
    python dependency_conflict_resolver.py
    python dependency_conflict_resolver.py --fix
    python dependency_conflict_resolver.py --report conflicts.json

Author: AstraGuard AI Team
Event: Elite Coders Winter of Code (Apertre 3.0) 2026
Issue: #710
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from packaging import version
from packaging.specifiers import SpecifierSet, InvalidSpecifier
from packaging.requirements import Requirement, InvalidRequirement


@dataclass
class DependencyInfo:
    """Information about a package dependency."""
    name: str
    version_spec: str
    source_file: str
    line_number: int
    extras: List[str] = None
    
    def __post_init__(self):
        if self.extras is None:
            self.extras = []


@dataclass
class Conflict:
    """Represents a dependency conflict."""
    package: str
    conflicts: List[DependencyInfo]
    conflict_type: str  # "version", "missing", "incompatible"
    severity: str  # "critical", "high", "medium", "low"
    suggested_resolution: str
    details: str


class DependencyConflictResolver:
    """Resolves dependency conflicts across requirements files."""
    
    def __init__(self, root_dir: Path = None):
        """
        Initialize the resolver.
        
        Args:
            root_dir: Root directory of the project (defaults to current dir)
        """
        self.root_dir = root_dir or Path.cwd()
        self.dependencies: Dict[str, List[DependencyInfo]] = defaultdict(list)
        self.conflicts: List[Conflict] = []
        self.requirements_files: List[Path] = []
        
    def find_requirements_files(self) -> List[Path]:
        """
        Find all requirements*.txt files in the project.
        
        Returns:
            List of paths to requirements files
        """
        patterns = [
            "requirements.txt",
            "requirements-*.txt",
            "**/requirements.txt",
            "**/requirements-*.txt",
        ]
        
        found_files = []
        for pattern in patterns:
            found_files.extend(self.root_dir.glob(pattern))
        
        # Deduplicate and sort
        unique_files = sorted(set(found_files))
        self.requirements_files = unique_files
        return unique_files
    
    def parse_requirements_file(self, file_path: Path) -> List[DependencyInfo]:
        """
        Parse a requirements file and extract dependencies.
        
        Args:
            file_path: Path to requirements file
            
        Returns:
            List of DependencyInfo objects
        """
        deps = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    
                    # Skip comments and empty lines
                    if not line or line.startswith('#'):
                        continue
                    
                    # Remove inline comments
                    if '#' in line:
                        line = line.split('#')[0].strip()
                    
                    try:
                        # Parse using packaging library
                        req = Requirement(line)
                        
                        dep = DependencyInfo(
                            name=req.name.lower(),
                            version_spec=str(req.specifier) if req.specifier else "",
                            source_file=str(file_path.relative_to(self.root_dir)),
                            line_number=line_num,
                            extras=list(req.extras) if req.extras else []
                        )
                        deps.append(dep)
                        
                    except (InvalidRequirement, Exception) as e:
                        # Try basic parsing for simple cases
                        if '==' in line or '>=' in line or '<=' in line or '~=' in line:
                            match = re.match(r'^([a-zA-Z0-9_-]+)([><=!~]+.*)$', line)
                            if match:
                                pkg_name = match.group(1).lower()
                                version_spec = match.group(2)
                                
                                dep = DependencyInfo(
                                    name=pkg_name,
                                    version_spec=version_spec,
                                    source_file=str(file_path.relative_to(self.root_dir)),
                                    line_number=line_num
                                )
                                deps.append(dep)
        
        except FileNotFoundError:
            print(f"⚠️  Warning: File not found: {file_path}")
        except Exception as e:
            print(f"⚠️  Warning: Error parsing {file_path}: {e}")
        
        return deps
    
    def collect_all_dependencies(self) -> Dict[str, List[DependencyInfo]]:
        """
        Collect all dependencies from all requirements files.
        
        Returns:
            Dictionary mapping package names to list of DependencyInfo
        """
        files = self.find_requirements_files()
        
        for file_path in files:
            deps = self.parse_requirements_file(file_path)
            for dep in deps:
                self.dependencies[dep.name].append(dep)
        
        return self.dependencies
    
    def detect_version_conflicts(self) -> List[Conflict]:
        """
        Detect version conflicts between dependencies.
        
        Returns:
            List of Conflict objects
        """
        conflicts = []
        
        for package, dep_list in self.dependencies.items():
            if len(dep_list) <= 1:
                continue
            
            # Check for version conflicts
            specifiers = []
            for dep in dep_list:
                if dep.version_spec:
                    try:
                        spec = SpecifierSet(dep.version_spec)
                        specifiers.append((spec, dep))
                    except InvalidSpecifier:
                        pass
            
            # Check if specifiers are compatible
            if len(specifiers) >= 2:
                is_compatible, details = self._check_specifier_compatibility(specifiers)
                
                if not is_compatible:
                    conflict = Conflict(
                        package=package,
                        conflicts=dep_list,
                        conflict_type="version",
                        severity=self._determine_severity(package, dep_list),
                        suggested_resolution=self._suggest_resolution(package, dep_list),
                        details=details
                    )
                    conflicts.append(conflict)
        
        self.conflicts.extend(conflicts)
        return conflicts
    
    def _check_specifier_compatibility(
        self, 
        specifiers: List[Tuple[SpecifierSet, DependencyInfo]]
    ) -> Tuple[bool, str]:
        """
        Check if multiple version specifiers are compatible.
        
        Args:
            specifiers: List of (SpecifierSet, DependencyInfo) tuples
            
        Returns:
            Tuple of (is_compatible, details_message)
        """
        if len(specifiers) < 2:
            return True, "No conflict"
        
        # Combine all specifiers
        combined = specifiers[0][0]
        for spec, dep in specifiers[1:]:
            try:
                # Check if there's any version that satisfies all specifiers
                combined = combined & spec
            except Exception:
                pass
        
        # Check if combined specifier is empty (no compatible versions)
        # Test with a range of version numbers
        test_versions = [
            "0.1.0", "1.0.0", "2.0.0", "3.0.0", "4.0.0", "5.0.0",
            "1.5.0", "2.5.0", "3.5.0", "4.5.0"
        ]
        
        compatible_versions = []
        for test_v in test_versions:
            if version.parse(test_v) in combined:
                compatible_versions.append(test_v)
        
        if not compatible_versions:
            # Build details message
            details = "Incompatible version specifiers:\n"
            for spec, dep in specifiers:
                details += f"  • {spec} (from {dep.source_file}:{dep.line_number})\n"
            return False, details
        
        return True, "Compatible"
    
    def _determine_severity(
        self, 
        package: str, 
        dep_list: List[DependencyInfo]
    ) -> str:
        """
        Determine the severity of a conflict.
        
        Args:
            package: Package name
            dep_list: List of conflicting dependencies
            
        Returns:
            Severity level: "critical", "high", "medium", or "low"
        """
        critical_packages = {
            'numpy', 'pandas', 'torch', 'fastapi', 'pydantic',
            'sqlalchemy', 'redis', 'pytest'
        }
        
        high_priority_packages = {
            'scikit-learn', 'aiohttp', 'httpx', 'uvicorn',
            'prometheus-client', 'opentelemetry-api'
        }
        
        if package in critical_packages:
            return "critical"
        elif package in high_priority_packages:
            return "high"
        elif len(dep_list) > 3:
            return "high"
        elif len(dep_list) > 2:
            return "medium"
        else:
            return "low"
    
    def _suggest_resolution(
        self, 
        package: str, 
        dep_list: List[DependencyInfo]
    ) -> str:
        """
        Suggest a resolution strategy for a conflict.
        
        Args:
            package: Package name
            dep_list: List of conflicting dependencies
            
        Returns:
            Suggested resolution as a string
        """
        # Extract version numbers from specifiers
        versions = []
        for dep in dep_list:
            if '==' in dep.version_spec:
                # Extract exact version
                v = dep.version_spec.replace('==', '').strip()
                try:
                    versions.append((version.parse(v), dep))
                except:
                    pass
        
        if versions:
            # Suggest using the latest version
            latest = max(versions, key=lambda x: x[0])
            return f"Use {package}=={latest[0]} across all requirements files"
        
        # Check for range specifiers
        has_range = any('>=' in dep.version_spec or '<' in dep.version_spec 
                       for dep in dep_list)
        
        if has_range:
            return f"Consolidate to a single compatible range (e.g., {package}>=X.Y.Z,<X+1.0.0)"
        
        return f"Standardize {package} version across all requirements files"
    
    def detect_missing_in_prod(self) -> List[Conflict]:
        """
        Detect packages used in dev/test but not in production requirements.
        
        Returns:
            List of Conflict objects
        """
        conflicts = []
        
        # Find production requirements file
        prod_files = [f for f in self.requirements_files 
                     if 'requirements.txt' in f.name and 'dev' not in f.name 
                     and 'test' not in f.name and 'ci' not in f.name]
        
        if not prod_files:
            return conflicts
        
        prod_file = prod_files[0]
        prod_deps = {dep.name for dep in self.parse_requirements_file(prod_file)}
        
        # Check other files
        for req_file in self.requirements_files:
            if req_file == prod_file:
                continue
            
            deps = self.parse_requirements_file(req_file)
            for dep in deps:
                if dep.name not in prod_deps:
                    # This is expected for dev/test dependencies
                    continue
        
        return conflicts
    
    def check_python_compatibility(self) -> List[Conflict]:
        """
        Check if dependencies are compatible with required Python version.
        
        Returns:
            List of Conflict objects
        """
        conflicts = []
        
        # Read Python version from pyproject.toml
        pyproject_file = self.root_dir / "pyproject.toml"
        min_python_version = None
        
        if pyproject_file.exists():
            with open(pyproject_file, 'r') as f:
                content = f.read()
                match = re.search(r'requires-python\s*=\s*["\']>=([^"\']+)["\']', content)
                if match:
                    min_python_version = match.group(1)
        
        if min_python_version:
            # Known incompatibilities (expand as needed)
            python_incompatibilities = {
                'scikit-learn': {
                    '1.8.0': '3.11',  # requires Python 3.11+
                },
                'numpy': {
                    '2.0.0': '3.10',  # requires Python 3.10+
                }
            }
            
            for package, versions_dict in python_incompatibilities.items():
                if package in self.dependencies:
                    for dep in self.dependencies[package]:
                        if '==' in dep.version_spec:
                            pkg_version = dep.version_spec.replace('==', '').strip()
                            if pkg_version in versions_dict:
                                required_py = versions_dict[pkg_version]
                                if version.parse(min_python_version) < version.parse(required_py):
                                    conflict = Conflict(
                                        package=package,
                                        conflicts=[dep],
                                        conflict_type="incompatible",
                                        severity="critical",
                                        suggested_resolution=f"Downgrade {package} to a version compatible with Python {min_python_version}+",
                                        details=f"{package}=={pkg_version} requires Python {required_py}+, but project requires Python {min_python_version}+"
                                    )
                                    conflicts.append(conflict)
        
        self.conflicts.extend(conflicts)
        return conflicts
    
    def generate_report(self) -> Dict:
        """
        Generate a comprehensive conflict report.
        
        Returns:
            Dictionary containing report data
        """
        report = {
            "summary": {
                "total_packages": len(self.dependencies),
                "total_conflicts": len(self.conflicts),
                "critical_conflicts": sum(1 for c in self.conflicts if c.severity == "critical"),
                "high_conflicts": sum(1 for c in self.conflicts if c.severity == "high"),
                "medium_conflicts": sum(1 for c in self.conflicts if c.severity == "medium"),
                "low_conflicts": sum(1 for c in self.conflicts if c.severity == "low"),
                "requirements_files": [str(f.relative_to(self.root_dir)) 
                                      for f in self.requirements_files]
            },
            "conflicts": [
                {
                    "package": c.package,
                    "type": c.conflict_type,
                    "severity": c.severity,
                    "details": c.details,
                    "suggested_resolution": c.suggested_resolution,
                    "affected_files": [
                        {
                            "file": dep.source_file,
                            "line": dep.line_number,
                            "version_spec": dep.version_spec
                        }
                        for dep in c.conflicts
                    ]
                }
                for c in self.conflicts
            ],
            "dependencies": {
                pkg: [
                    {
                        "version_spec": dep.version_spec,
                        "source": dep.source_file,
                        "line": dep.line_number
                    }
                    for dep in deps
                ]
                for pkg, deps in self.dependencies.items()
            }
        }
        
        return report
    
    def print_report(self):
        """Print a human-readable conflict report."""
        print("\n" + "="*80)
        print("🔍 DEPENDENCY CONFLICT ANALYSIS REPORT")
        print("="*80 + "\n")
        
        print(f"📁 Requirements Files Analyzed: {len(self.requirements_files)}")
        for f in self.requirements_files:
            print(f"   • {f.relative_to(self.root_dir)}")
        
        print(f"\n📦 Total Packages: {len(self.dependencies)}")
        print(f"⚠️  Total Conflicts: {len(self.conflicts)}\n")
        
        if not self.conflicts:
            print("✅ No conflicts detected! All dependencies are compatible.\n")
            return
        
        # Group by severity
        severity_groups = {
            "critical": [],
            "high": [],
            "medium": [],
            "low": []
        }
        
        for conflict in self.conflicts:
            severity_groups[conflict.severity].append(conflict)
        
        # Print conflicts by severity
        severity_icons = {
            "critical": "🔴",
            "high": "🟠",
            "medium": "🟡",
            "low": "🟢"
        }
        
        for severity in ["critical", "high", "medium", "low"]:
            conflicts = severity_groups[severity]
            if not conflicts:
                continue
            
            print(f"{severity_icons[severity]} {severity.upper()} SEVERITY ({len(conflicts)} conflicts)")
            print("-" * 80)
            
            for i, conflict in enumerate(conflicts, 1):
                print(f"\n{i}. Package: {conflict.package}")
                print(f"   Type: {conflict.conflict_type}")
                print(f"   Details: {conflict.details}")
                print(f"\n   Conflicting Dependencies:")
                for dep in conflict.conflicts:
                    print(f"      • {dep.name}{dep.version_spec}")
                    print(f"        from {dep.source_file}:{dep.line_number}")
                print(f"\n   💡 Suggested Resolution:")
                print(f"      {conflict.suggested_resolution}")
                print()
        
        print("="*80 + "\n")
    
    def auto_fix_conflicts(self, dry_run: bool = True) -> List[str]:
        """
        Automatically fix conflicts where possible.
        
        Args:
            dry_run: If True, only show what would be changed
            
        Returns:
            List of changes made/proposed
        """
        changes = []
        
        print(f"\n{'🔍 DRY RUN MODE' if dry_run else '🔧 AUTO-FIX MODE'}")
        print("="*80 + "\n")
        
        for conflict in self.conflicts:
            if conflict.conflict_type != "version":
                continue
            
            # For version conflicts, use the latest version
            versions_with_deps = []
            for dep in conflict.conflicts:
                if '==' in dep.version_spec:
                    v = dep.version_spec.replace('==', '').strip()
                    try:
                        parsed_v = version.parse(v)
                        versions_with_deps.append((parsed_v, dep))
                    except:
                        pass
            
            if versions_with_deps:
                latest_version, _ = max(versions_with_deps, key=lambda x: x[0])
                
                change_desc = f"Standardize {conflict.package} to =={latest_version}"
                changes.append(change_desc)
                print(f"✓ {change_desc}")
                
                if not dry_run:
                    # Apply changes to files
                    for dep in conflict.conflicts:
                        if dep.version_spec != f"=={latest_version}":
                            self._update_requirement_in_file(
                                Path(self.root_dir / dep.source_file),
                                dep.name,
                                f"=={latest_version}",
                                dep.line_number
                            )
                            print(f"   Updated {dep.source_file}:{dep.line_number}")
        
        if dry_run:
            print(f"\n💡 To apply these changes, run with --fix flag")
        else:
            print(f"\n✅ Applied {len(changes)} fixes")
        
        return changes
    
    def _update_requirement_in_file(
        self, 
        file_path: Path, 
        package: str, 
        new_spec: str,
        line_number: int
    ):
        """
        Update a requirement in a file.
        
        Args:
            file_path: Path to requirements file
            package: Package name
            new_spec: New version specifier
            line_number: Line number to update
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Update the specific line
            if 1 <= line_number <= len(lines):
                line = lines[line_number - 1]
                # Replace version specifier
                new_line = re.sub(
                    r'([a-zA-Z0-9_-]+)([><=!~]+[^\s#]*)',
                    f'{package}{new_spec}',
                    line
                )
                lines[line_number - 1] = new_line
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
        
        except Exception as e:
            print(f"⚠️  Error updating {file_path}: {e}")


def main():
    """Main entry point for the dependency conflict resolver."""
    parser = argparse.ArgumentParser(
        description="Detect and resolve dependency conflicts in AstraGuard AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze dependencies and show conflicts
  python dependency_conflict_resolver.py
  
  # Show what would be fixed (dry run)
  python dependency_conflict_resolver.py --fix --dry-run
  
  # Auto-fix conflicts
  python dependency_conflict_resolver.py --fix
  
  # Export report to JSON
  python dependency_conflict_resolver.py --report conflicts.json
        """
    )
    
    parser.add_argument(
        '--fix',
        action='store_true',
        help='Auto-fix conflicts where possible'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be fixed without making changes'
    )
    
    parser.add_argument(
        '--report',
        type=str,
        metavar='FILE',
        help='Export report to JSON file'
    )
    
    parser.add_argument(
        '--root',
        type=str,
        metavar='DIR',
        help='Project root directory (default: current directory)'
    )
    
    args = parser.parse_args()
    
    # Initialize resolver
    root_dir = Path(args.root) if args.root else Path.cwd()
    resolver = DependencyConflictResolver(root_dir)
    
    print("\n🚀 AstraGuard AI - Dependency Conflict Resolver")
    print("Elite Coders Winter of Code (Apertre 3.0) 2026")
    print("Issue #710\n")
    
    # Collect dependencies
    print("📦 Collecting dependencies...")
    resolver.collect_all_dependencies()
    
    # Detect conflicts
    print("🔍 Detecting version conflicts...")
    resolver.detect_version_conflicts()
    
    print("🔍 Checking Python compatibility...")
    resolver.check_python_compatibility()
    
    # Print report
    resolver.print_report()
    
    # Export report if requested
    if args.report:
        report = resolver.generate_report()
        with open(args.report, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
        print(f"📄 Report exported to: {args.report}\n")
    
    # Auto-fix if requested
    if args.fix or args.dry_run:
        resolver.auto_fix_conflicts(dry_run=not args.fix or args.dry_run)
    
    # Exit with error code if conflicts found
    if resolver.conflicts:
        critical_or_high = sum(1 for c in resolver.conflicts 
                              if c.severity in ["critical", "high"])
        if critical_or_high > 0:
            sys.exit(1)
    
    sys.exit(0)


if __name__ == "__main__":
    main()
