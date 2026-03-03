"""
Issue Labeling System for AstraGuard AI
========================================

Provides a comprehensive labeling system for GitHub issues with:
- Predefined label categories and types
- Label validation and management
- Issue classification and labeling suggestions
- Integration with GitHub CLI

Author: AstraGuard AI Team
License: MIT
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Set, Tuple
import json
import re


class IssueDifficulty(Enum):
    """Issue difficulty levels"""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class IssueCategory(Enum):
    """Issue categories based on type of work"""
    DOCUMENTATION = "documentation"
    FRONTEND = "frontend"
    BACKEND = "backend"
    TESTING = "testing"
    CONFIGURATION = "configuration"
    CODE_QUALITY = "code-quality"
    BUG = "bug"
    FEATURE = "feature"
    SECURITY = "security"
    PERFORMANCE = "performance"
    DEVOPS = "devops"
    COMMUNITY = "community"


class IssueStatus(Enum):
    """Issue status labels"""
    GOOD_FIRST_ISSUE = "good first issue"
    HELP_WANTED = "help wanted"
    IN_PROGRESS = "in-progress"
    BLOCKED = "blocked"
    DUPLICATE = "duplicate"
    WONTFIX = "wontfix"


class Priority(Enum):
    """Issue priority levels"""
    CRITICAL = "priority: critical"
    HIGH = "priority: high"
    MEDIUM = "priority: medium"
    LOW = "priority: low"


class IssueType(Enum):
    """Specific issue types for more granular classification"""
    # Documentation Types
    DOCSTRING = "type: docstring"
    COMMENT = "type: comment"
    README = "type: readme"
    API_DOCS = "type: api-docs"
    
    # Code Types
    REFACTOR = "type: refactor"
    TYPING = "type: typing"
    LINTING = "type: linting"
    
    # Testing Types
    UNIT_TEST = "type: unit-test"
    INTEGRATION_TEST = "type: integration-test"
    E2E_TEST = "type: e2e-test"
    
    # Bug Types
    BUG_LOGIC = "type: bug-logic"
    BUG_CRASH = "type: bug-crash"
    BUG_SECURITY = "type: bug-security"
    
    # Feature Types
    FEATURE_NEW = "type: feature-new"
    FEATURE_ENHANCE = "type: feature-enhance"
    
    # Performance Types
    OPTIMIZATION = "type: optimization"
    PROFILING = "type: profiling"


@dataclass
class Label:
    """Represents a GitHub label with metadata"""
    name: str
    description: str
    color: str
    category: str
    
    def __hash__(self):
        return hash(self.name)
    
    def __eq__(self, other):
        if isinstance(other, Label):
            return self.name == other.name
        elif isinstance(other, str):
            return self.name == other
        return False


@dataclass
class LabelSet:
    """A set of labels with validation and management"""
    labels: Dict[str, Label] = field(default_factory=dict)
    
    def add_label(self, label: Label) -> None:
        """Add a label to the set"""
        self.labels[label.name] = label
    
    def get_label(self, name: str) -> Optional[Label]:
        """Get a label by name"""
        return self.labels.get(name)
    
    def get_labels_by_category(self, category: str) -> List[Label]:
        """Get all labels in a category"""
        return [label for label in self.labels.values() if label.category == category]
    
    def validate_labels(self, labels: List[str]) -> Tuple[bool, List[str]]:
        """
        Validate a list of label names
        Returns: (is_valid, list_of_invalid_labels)
        """
        invalid = [label for label in labels if label not in self.labels]
        return len(invalid) == 0, invalid
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            name: {
                'description': label.description,
                'color': label.color,
                'category': label.category
            }
            for name, label in self.labels.items()
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'LabelSet':
        """Create LabelSet from dictionary"""
        label_set = cls()
        for name, info in data.items():
            label = Label(
                name=name,
                description=info.get('description', ''),
                color=info.get('color', '000000'),
                category=info.get('category', 'other')
            )
            label_set.add_label(label)
        return label_set


class IssueClassifier:
    """Classifies issues and suggests appropriate labels"""
    
    def __init__(self):
        self.keywords_difficulty = {
            'easy': ['simple', 'easy', 'trivial', 'basic', 'beginner', 'starter'],
            'medium': ['moderate', 'medium', 'intermediate', 'standard', 'typical'],
            'hard': ['complex', 'hard', 'difficult', 'challenging', 'advanced', 'expert']
        }
        
        self.keywords_category = {
            'documentation': ['doc', 'docstring', 'readme', 'comment', 'explanation', 'guide', 'tutorial'],
            'frontend': ['ui', 'ux', 'frontend', 'react', 'css', 'style', 'button', 'component'],
            'backend': ['backend', 'api', 'server', 'service', 'database', 'db', 'query'],
            'testing': ['test', 'unittest', 'pytest', 'coverage', 'mock', 'fixture'],
            'configuration': ['config', 'setup', 'environment', 'variable', 'settings'],
            'code-quality': ['quality', 'refactor', 'cleanup', 'lint', 'format', 'style'],
            'bug': ['bug', 'issue', 'error', 'crash', 'fail', 'broken', 'regression'],
            'feature': ['feature', 'enhancement', 'add', 'implement', 'new', 'capability'],
            'security': ['security', 'vulnerability', 'auth', 'encrypt', 'permission'],
            'performance': ['performance', 'optimize', 'speed', 'benchmark', 'latency'],
            'devops': ['deploy', 'ci', 'cd', 'docker', 'kubernetes', 'infra', 'monitoring'],
            'community': ['community', 'contribution', 'contributor', 'discussion']
        }
        
        self.keywords_type = {
            'type: docstring': ['docstring', 'function documentation', 'class documentation'],
            'type: typing': ['type hint', 'annotation', 'type check', 'mypy'],
            'type: refactor': ['refactor', 'reorganize', 'restructure', 'simplify'],
            'type: unit-test': ['unit test', 'unittest', 'test case'],
            'type: integration-test': ['integration', 'integration test'],
            'type: optimization': ['optimize', 'performance', 'improve speed'],
        }
        
        self.keywords_good_first = [
            'good first', 'beginner', 'starter', 'help wanted', 'simple',
            'documentation', 'typo', 'comment', 'docstring'
        ]
    
    def classify_difficulty(self, title: str, body: str) -> Optional[str]:
        """Classify issue difficulty from content"""
        text = f"{title} {body}".lower()
        
        for difficulty, keywords in self.keywords_difficulty.items():
            if any(kw in text for kw in keywords):
                return difficulty
        return None
    
    def classify_category(self, title: str, body: str) -> Optional[str]:
        """Classify issue category from content"""
        text = f"{title} {body}".lower()
        
        # Score each category by keyword matches
        scores = {}
        for category, keywords in self.keywords_category.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                scores[category] = score
        
        if scores:
            return max(scores, key=scores.get)
        return None
    
    def classify_issue_type(self, title: str, body: str) -> List[str]:
        """Classify specific issue types from content"""
        text = f"{title} {body}".lower()
        matched_types = []
        
        for issue_type, keywords in self.keywords_type.items():
            if any(kw in text for kw in keywords):
                matched_types.append(issue_type)
        
        return matched_types
    
    def suggest_labels(self, title: str, body: str, 
                      difficulty: Optional[str] = None,
                      category: Optional[str] = None) -> List[str]:
        """
        Suggest labels for an issue based on its content
        
        Args:
            title: Issue title
            body: Issue body/description
            difficulty: Override difficulty classification
            category: Override category classification
        
        Returns:
            List of suggested label names
        """
        suggestions = []
        
        # Get or classify difficulty
        if not difficulty:
            difficulty = self.classify_difficulty(title, body)
        if difficulty:
            suggestions.append(f"difficulty: {difficulty}")
        
        # Get or classify category
        if not category:
            category = self.classify_category(title, body)
        if category:
            suggestions.append(category)
        
        # Add specific types
        issue_types = self.classify_issue_type(title, body)
        suggestions.extend(issue_types)
        
        # Check if it's a good first issue
        text = f"{title} {body}".lower()
        if any(kw in text for kw in self.keywords_good_first):
            suggestions.append("good first issue")
        
        # Remove duplicates while preserving order
        seen = set()
        result = []
        for label in suggestions:
            if label not in seen:
                seen.add(label)
                result.append(label)
        
        return result


class LabelManager:
    """Manages label operations"""
    
    def __init__(self, label_set: LabelSet):
        self.label_set = label_set
        self.classifier = IssueClassifier()
    
    def get_all_labels(self) -> List[Label]:
        """Get all available labels"""
        return list(self.label_set.labels.values())
    
    def get_labels_by_category(self, category: str) -> List[Label]:
        """Get labels in a specific category"""
        return self.label_set.get_labels_by_category(category)
    
    def suggest_for_issue(self, title: str, body: str) -> List[str]:
        """Suggest labels for an issue"""
        return self.classifier.suggest_labels(title, body)
    
    def validate_labels(self, labels: List[str]) -> Tuple[bool, List[str]]:
        """Validate labels"""
        return self.label_set.validate_labels(labels)
    
    def get_label_info(self, label_name: str) -> Optional[Dict]:
        """Get detailed info about a label"""
        label = self.label_set.get_label(label_name)
        if not label:
            return None
        return {
            'name': label.name,
            'description': label.description,
            'color': label.color,
            'category': label.category
        }


# ============================================================================
# Predefined Label Sets
# ============================================================================

def create_default_label_set() -> LabelSet:
    """Create the default label set for AstraGuard AI"""
    label_set = LabelSet()
    
    # Difficulty Labels
    difficulty_labels = [
        Label('difficulty: easy', 'Good for beginners', 'a2eeef', 'difficulty'),
        Label('difficulty: medium', 'Moderate complexity', '008672', 'difficulty'),
        Label('difficulty: hard', 'Advanced or complex', '9d1a1a', 'difficulty'),
    ]
    
    # Category Labels
    category_labels = [
        Label('documentation', 'Documentation improvements', 'fbca04', 'category'),
        Label('frontend', 'UI/Frontend changes', 'd876e3', 'category'),
        Label('backend', 'Backend/API changes', '0052cc', 'category'),
        Label('testing', 'Test coverage and quality', '1d76db', 'category'),
        Label('configuration', 'Configuration and setup', 'fef2c0', 'category'),
        Label('code-quality', 'Code quality improvements', 'cce5ff', 'category'),
        Label('bug', 'Something is broken', 'f9d0c4', 'category'),
        Label('feature', 'New feature or request', 'a2eeef', 'category'),
        Label('security', 'Security-related issues', 'ee0701', 'category'),
        Label('performance', 'Performance optimization', 'fdb3c1', 'category'),
        Label('devops', 'DevOps and infrastructure', 'b60205', 'category'),
        Label('community', 'Community and contribution', '5ebeff', 'category'),
    ]
    
    # Status Labels
    status_labels = [
        Label('good first issue', 'Good for newcomers', '7057ff', 'status'),
        Label('help wanted', 'Help needed', '33aa3f', 'status'),
        Label('in-progress', 'Currently being worked on', 'f9d0c4', 'status'),
        Label('blocked', 'Blocked by another issue', '9e9e9e', 'status'),
        Label('duplicate', 'Duplicate of another issue', 'e6e6e6', 'status'),
        Label('wontfix', 'Will not be fixed', 'ffffff', 'status'),
    ]
    
    # Priority Labels
    priority_labels = [
        Label('priority: critical', 'Blocker for deployment', 'b60205', 'priority'),
        Label('priority: high', 'Should be addressed soon', 'd4c5f9', 'priority'),
        Label('priority: medium', 'Normal priority', 'fbca04', 'priority'),
        Label('priority: low', 'Nice to have', 'c2e0c6', 'priority'),
    ]
    
    # Type Labels
    type_labels = [
        Label('type: docstring', 'Docstring/documentation', 'fad8c7', 'type'),
        Label('type: comment', 'Comment improvements', 'fad8c7', 'type'),
        Label('type: readme', 'README updates', 'fad8c7', 'type'),
        Label('type: api-docs', 'API documentation', 'fad8c7', 'type'),
        Label('type: refactor', 'Code refactoring', 'fbca04', 'type'),
        Label('type: typing', 'Type hints/annotations', 'fbca04', 'type'),
        Label('type: linting', 'Code style/linting', 'fbca04', 'type'),
        Label('type: unit-test', 'Unit testing', 'c5def5', 'type'),
        Label('type: integration-test', 'Integration testing', 'c5def5', 'type'),
        Label('type: e2e-test', 'End-to-end testing', 'c5def5', 'type'),
        Label('type: bug-logic', 'Logic error', 'ee0701', 'type'),
        Label('type: bug-crash', 'Crash or hang', 'ee0701', 'type'),
        Label('type: bug-security', 'Security vulnerability', 'ee0701', 'type'),
        Label('type: feature-new', 'New feature', '1d76db', 'type'),
        Label('type: feature-enhance', 'Feature enhancement', '1d76db', 'type'),
        Label('type: optimization', 'Performance optimization', 'fdb3c1', 'type'),
        Label('type: profiling', 'Performance profiling', 'fdb3c1', 'type'),
    ]
    
    # Project Labels
    project_labels = [
        Label('apertre3.0', 'Apertre 3.0 project', 'blueviolet', 'project'),
    ]
    
    # Skills/Expertise Labels
    skills_labels = [
        Label('enhancement', 'Code enhancement', '84b6eb', 'skills'),
        Label('optimization', 'Performance optimization', 'fdb3c1', 'skills'),
        Label('refactor', 'Code refactoring', 'fbca04', 'skills'),
        Label('quality', 'Quality improvement', 'cce5ff', 'skills'),
        Label('monitoring', 'Monitoring and observability', 'b60205', 'skills'),
    ]
    
    # Add all labels to the set
    all_labels = (difficulty_labels + category_labels + status_labels + 
                  priority_labels + type_labels + project_labels + skills_labels)
    
    for label in all_labels:
        label_set.add_label(label)
    
    return label_set


# ============================================================================
# Utility Functions
# ============================================================================

def get_default_label_manager() -> LabelManager:
    """Get a LabelManager with the default label set"""
    label_set = create_default_label_set()
    return LabelManager(label_set)


def export_label_config(label_set: LabelSet, filepath: str) -> None:
    """Export label configuration to JSON file"""
    config = label_set.to_dict()
    with open(filepath, 'w') as f:
        json.dump(config, f, indent=2)


def import_label_config(filepath: str) -> LabelSet:
    """Import label configuration from JSON file"""
    with open(filepath, 'r') as f:
        config = json.load(f)
    return LabelSet.from_dict(config)


if __name__ == "__main__":
    # Example usage
    print("=== AstraGuard AI Issue Labeling System ===\n")
    
    # Create label manager
    manager = get_default_label_manager()
    
    # Show all labels
    print("Available Labels:")
    for label in manager.get_all_labels():
        print(f"  • {label.name}: {label.description}")
    
    print("\n" + "="*50 + "\n")
    
    # Test label suggestion
    test_title = "Add type hints to anomaly_detector.py"
    test_body = "We need to improve code reliability by adding full type annotation coverage."
    
    print(f"Issue Title: {test_title}")
    print(f"Issue Body: {test_body}\n")
    
    suggestions = manager.suggest_for_issue(test_title, test_body)
    print("Suggested Labels:")
    for label in suggestions:
        print(f"  • {label}")
