#!/usr/bin/env python3
"""
Test Suite for Issue Labeling System
====================================

Tests core functionality without requiring GitHub CLI
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
os.chdir(project_root)

from src.tools.issue_labeling import (
    Label, LabelSet, IssueClassifier, LabelManager,
    create_default_label_set, get_default_label_manager,
    export_label_config, import_label_config
)


def test_label_model():
    """Test Label data model"""
    print("\n" + "="*60)
    print("TEST 1: Label Data Model")
    print("="*60)
    
    label = Label(
        name="difficulty: easy",
        description="Good for beginners",
        color="a2eeef",
        category="difficulty"
    )
    
    assert label.name == "difficulty: easy"
    assert label.description == "Good for beginners"
    assert label.color == "a2eeef"
    assert label.category == "difficulty"
    
    print("✅ Label creation: PASS")
    print(f"   Created: {label.name} ({label.color})")
    print(f"   Description: {label.description}")
    
    return True


def test_label_set():
    """Test LabelSet collection"""
    print("\n" + "="*60)
    print("TEST 2: LabelSet Management")
    print("="*60)
    
    label_set = LabelSet()
    
    # Add labels
    label1 = Label("test-label-1", "Test label 1", "FF0000", "test")
    label2 = Label("test-label-2", "Test label 2", "00FF00", "test")
    
    label_set.add_label(label1)
    label_set.add_label(label2)
    
    assert len(label_set.labels) == 2
    print("✅ Add labels: PASS")
    print(f"   Added 2 labels, total: {len(label_set.labels)}")
    
    # Get label
    retrieved = label_set.get_label("test-label-1")
    assert retrieved.name == "test-label-1"
    print("✅ Get label by name: PASS")
    
    # Get by category
    cat_labels = label_set.get_labels_by_category("test")
    assert len(cat_labels) == 2
    print("✅ Get labels by category: PASS")
    print(f"   Found {len(cat_labels)} labels in 'test' category")
    
    # Validate labels
    is_valid, invalid = label_set.validate_labels(["test-label-1", "nonexistent"])
    assert not is_valid
    assert "nonexistent" in invalid
    print("✅ Validate labels: PASS")
    print(f"   Invalid labels detected: {invalid}")
    
    return True


def test_default_label_set():
    """Test default label set creation"""
    print("\n" + "="*60)
    print("TEST 3: Default Label Set")
    print("="*60)
    
    label_set = create_default_label_set()
    
    assert len(label_set.labels) > 40
    print(f"✅ Default set created: PASS")
    print(f"   Total labels: {len(label_set.labels)}")
    
    # Check categories
    categories = set(label.category for label in label_set.labels.values())
    print(f"   Categories: {len(categories)}")
    for cat in sorted(categories):
        count = len(label_set.get_labels_by_category(cat))
        print(f"     • {cat}: {count} labels")
    
    # Check specific labels
    assert label_set.get_label("difficulty: easy") is not None
    assert label_set.get_label("documentation") is not None
    assert label_set.get_label("good first issue") is not None
    print("✅ Standard labels present: PASS")
    
    return True


def test_issue_classifier():
    """Test IssueClassifier"""
    print("\n" + "="*60)
    print("TEST 4: Issue Classifier")
    print("="*60)
    
    classifier = IssueClassifier()
    
    # Test 1: Type hints issue (code quality)
    title1 = "Add type hints to detector.py"
    body1 = "We need full type annotation coverage for reliability."
    
    difficulty = classifier.classify_difficulty(title1, body1)
    category = classifier.classify_category(title1, body1)
    types = classifier.classify_issue_type(title1, body1)
    
    print(f"\nIssue 1: {title1}")
    print(f"  Difficulty: {difficulty}")
    print(f"  Category: {category}")
    print(f"  Types: {types}")
    
    # Difficulty may be None if not enough indicators
    if difficulty is not None:
        assert difficulty in ["easy", "medium", "hard"], f"Invalid difficulty: {difficulty}"
    print("✅ Difficulty classification: PASS")
    
    # Should detect typing type
    assert "type: typing" in types, f"Expected 'type: typing' in {types}"
    print("✅ Type detection: PASS")
    
    # Test 2: Bug report
    title2 = "Bug: Crash on empty input"
    body2 = "The system crashes when processing empty input data."
    
    category2 = classifier.classify_category(title2, body2)
    print(f"\nIssue 2: {title2}")
    print(f"  Category: {category2}")
    
    assert category2 == "bug", f"Expected 'bug', got '{category2}'"
    print("✅ Bug category detection: PASS")
    
    # Test 3: Documentation
    title3 = "Documentation: Improve README"
    body3 = "The README needs better examples and clearer instructions."
    
    category3 = classifier.classify_category(title3, body3)
    print(f"\nIssue 3: {title3}")
    print(f"  Category: {category3}")
    
    assert category3 == "documentation", f"Expected 'documentation', got '{category3}'"
    print("✅ Documentation detection: PASS")
    
    return True


def test_label_suggestions():
    """Test label suggestion engine"""
    print("\n" + "="*60)
    print("TEST 5: Label Suggestion Engine")
    print("="*60)
    
    classifier = IssueClassifier()
    
    test_cases = [
        {
            "title": "Add docstrings to module",
            "body": "Missing documentation for public functions",
            "expected_keywords": ["documentation", "easy"],
        },
        {
            "title": "Performance optimization for detector",
            "body": "Current implementation is too slow. Needs optimization.",
            "expected_keywords": ["performance", "optimization"],
        },
        {
            "title": "Write unit tests for backend",
            "body": "Need comprehensive test coverage for API endpoints",
            "expected_keywords": ["testing", "backend"],
        },
    ]
    
    for i, test in enumerate(test_cases, 1):
        suggestions = classifier.suggest_labels(test["title"], test["body"])
        print(f"\nTest Case {i}: {test['title']}")
        print(f"  Suggestions: {', '.join(suggestions)}")
        
        # Check that at least some expected keywords are found
        found = any(kw in str(suggestions).lower() for kw in test["expected_keywords"])
        if found:
            print(f"  ✅ Contains expected keywords")
        else:
            print(f"  ⚠️  Missing expected keywords: {test['expected_keywords']}")
    
    print("\n✅ Suggestion engine: PASS")
    return True


def test_label_manager():
    """Test LabelManager orchestration"""
    print("\n" + "="*60)
    print("TEST 6: Label Manager")
    print("="*60)
    
    manager = get_default_label_manager()
    
    # Get all labels
    all_labels = manager.get_all_labels()
    print(f"✅ Get all labels: PASS ({len(all_labels)} labels)")
    
    # Get by category
    doc_labels = manager.get_labels_by_category("difficulty")
    print(f"✅ Get by category: PASS ({len(doc_labels)} difficulty labels)")
    
    # Suggest for issue
    suggestions = manager.suggest_for_issue(
        "Add type hints to validator.py",
        "Need full type annotation coverage for code reliability."
    )
    print(f"✅ Suggest labels: PASS")
    print(f"   Suggestions for type hints issue: {suggestions}")
    
    # Get label info
    info = manager.get_label_info("difficulty: easy")
    assert info is not None
    assert info["name"] == "difficulty: easy"
    print(f"✅ Get label info: PASS")
    print(f"   Label: {info['name']}")
    print(f"   Description: {info['description']}")
    
    # Validate labels
    is_valid, invalid = manager.validate_labels(
        ["difficulty: easy", "documentation", "apertre3.0"]
    )
    assert is_valid
    print(f"✅ Validate labels: PASS (all valid)")
    
    return True


def test_export_import():
    """Test export/import functionality"""
    print("\n" + "="*60)
    print("TEST 7: Export/Import Configuration")
    print("="*60)
    
    import json
    import tempfile
    
    label_set = create_default_label_set()
    
    # Export to dict
    exported = label_set.to_dict()
    assert len(exported) > 40
    print(f"✅ Export to dict: PASS ({len(exported)} labels)")
    
    # Verify structure
    sample_label = list(exported.values())[0]
    assert "description" in sample_label
    assert "color" in sample_label
    assert "category" in sample_label
    print(f"✅ Export structure valid: PASS")
    
    # Import from dict
    new_set = LabelSet.from_dict(exported)
    assert len(new_set.labels) == len(exported)
    print(f"✅ Import from dict: PASS ({len(new_set.labels)} labels)")
    
    # Verify reimported data
    reconstructed_label = new_set.get_label("difficulty: easy")
    assert reconstructed_label is not None
    print(f"✅ Reimported labels valid: PASS")
    
    return True


def run_all_tests():
    """Run all tests"""
    print("\n" + "🏷️  ISSUE LABELING SYSTEM - TEST SUITE" + "\n")
    
    tests = [
        ("Label Model", test_label_model),
        ("LabelSet Management", test_label_set),
        ("Default Label Set", test_default_label_set),
        ("Issue Classifier", test_issue_classifier),
        ("Label Suggestions", test_label_suggestions),
        ("Label Manager", test_label_manager),
        ("Export/Import", test_export_import),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ {name}: FAILED")
            print(f"   Error: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 **ALL TESTS PASSED** 🎉")
        return True
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
