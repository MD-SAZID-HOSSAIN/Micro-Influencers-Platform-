from apps.campaigns.eligibility import is_eligible
from apps.campaigns.models import Campaign


def campaign(platform="instagram", min_followers=None):
    return Campaign(platform=platform, min_followers=min_followers)


def test_eligible_when_platform_stat_exists_and_followers_meet_the_minimum():
    assert is_eligible(campaign(min_followers=1000), {"instagram": 1500}) is True


def test_eligible_when_followers_equal_the_minimum():
    assert is_eligible(campaign(min_followers=1000), {"instagram": 1000}) is True


def test_not_eligible_below_the_minimum():
    assert is_eligible(campaign(min_followers=1000), {"instagram": 999}) is False


def test_not_eligible_without_stats_for_the_campaign_platform():
    assert is_eligible(campaign("youtube", 100), {"instagram": 50000}) is False


def test_eligible_when_no_minimum_is_set_as_long_as_the_platform_has_stats():
    assert is_eligible(campaign(min_followers=None), {"instagram": 1}) is True
    assert is_eligible(campaign(min_followers=None), {"tiktok": 1}) is False


def test_zero_followers_with_no_minimum_is_still_eligible():
    assert is_eligible(campaign(min_followers=None), {"instagram": 0}) is True


def test_empty_stats_are_never_eligible():
    assert is_eligible(campaign(), {}) is False
