"""Basic tests to ensure the test framework is working."""

import sys
from pathlib import Path


def test_basic_functionality():
    """Test that basic Python functionality works."""
    assert 1 + 1 == 2
    assert 2 * 3 == 6
    assert "hello".upper() == "HELLO"


def test_path_imports():
    """Test that we can work with paths and imports."""
    # Add src directory to path for imports
    src_path = Path(__file__).parent.parent / "src"
    assert src_path.exists()
    assert (src_path / "malla").exists()
    assert (src_path / "malla" / "__init__.py").exists()


def test_basic_string_operations():
    """Test basic string operations."""
    test_string = "test_string"
    assert len(test_string) == 11
    assert test_string.startswith("test")
    assert test_string.endswith("string")