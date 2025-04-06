import pytest
import sys
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

def test_simple():
    """A simple test to verify that the test environment is working."""
    assert True

def test_import_app():
    """Test that we can import the app module."""
    try:
        from app import create_app
        assert callable(create_app)
    except ImportError as e:
        pytest.fail(f"Failed to import app module: {e}") 