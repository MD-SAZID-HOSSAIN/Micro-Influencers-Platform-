import pytest

from apps.social.tests.fakes import FakeYouTubeClient


@pytest.fixture
def fake_youtube(monkeypatch):
    """Replace the real YouTube client everywhere the services build one."""
    fake = FakeYouTubeClient()
    monkeypatch.setattr("apps.social.services.get_youtube_client", lambda: fake)
    return fake
