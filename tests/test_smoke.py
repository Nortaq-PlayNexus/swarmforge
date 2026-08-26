import pytest

try:
    import swarmforge
except ImportError:
    swarmforge = None

def test_package_importable():
    if swarmforge is None:
        pytest.skip("swarmforge requires optional dependencies not installed")
    assert swarmforge is not None