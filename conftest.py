import pytest


@pytest.fixture(autouse=True)
def _clear_cache():
    """Throttle counters live in the cache; keep tests independent of each other."""
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def run_on_commit(django_capture_on_commit_callbacks):
    """Execute transaction.on_commit callbacks inside a test (they are deferred otherwise).

    Usage: ``with run_on_commit(): client.post(...)``.
    """

    def _run():
        return django_capture_on_commit_callbacks(execute=True)

    return _run
