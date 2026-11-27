"""pytest configuration: adds a --runslow option so the 500 MB test only runs when asked."""

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--runslow", action="store_true", help="run slow tests (500 MB log)"
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: slow test, only runs with --runslow")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--runslow"):
        return
    skip_slow = pytest.mark.skip(reason="slow: run with --runslow")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)
