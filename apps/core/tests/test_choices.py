from apps.core.choices import Niche, Platform


def test_platform_values():
    assert set(Platform.values) == {"instagram", "youtube", "tiktok", "facebook"}


def test_niche_values():
    assert set(Niche.values) == {"fitness", "tech", "beauty", "food", "travel", "other"}
