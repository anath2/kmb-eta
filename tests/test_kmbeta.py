import pytest
from kmbeta import __version__
from kmbeta import main


@pytest.fixture
def test_stop():
    return "GREENFIELD COURT"


@pytest.fixture
def test_bus():
    return "88"


@pytest.fixture
def test_destination():
    return "SAU MAU PING (CENTRAL)"


def test_version():
    assert __version__ == "0.1.0"


def test_get_eta(test_stop, test_bus, test_destination):
    eta_data = main.get_eta(test_stop, test_bus, test_destination)
    assert eta_data
