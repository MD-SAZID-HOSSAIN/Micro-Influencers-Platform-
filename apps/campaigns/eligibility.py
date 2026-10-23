from apps.core.choices import Platform

from .models import Campaign


def is_eligible(campaign: Campaign, followers_by_platform: dict[str, int]) -> bool:
    """The "Eligible" / "Check fit" hint: does the creator have stats for the campaign's platform and enough followers?

    Verified and Unverified stats both count. This is only the hint; what blocks applying is
    ``minimum_followers_problem``.
    """
    followers = followers_by_platform.get(campaign.platform)
    if followers is None:
        return False
    return campaign.min_followers is None or followers >= campaign.min_followers


def minimum_followers_problem(campaign: Campaign, followers_by_platform: dict[str, int]) -> str | None:
    """Why the creator is under the campaign's minimum followers, or None.

    A verified YouTube creator may apply to a campaign on any platform, so a creator with no numbers on the
    campaign's platform is not blocked. When the numbers are there (YouTube, or Instagram, TikTok and Facebook an admin
    approved), they must reach the minimum the brand set.
    """
    followers = followers_by_platform.get(campaign.platform)
    if campaign.min_followers is None or followers is None or followers >= campaign.min_followers:
        return None
    platform = Platform(campaign.platform).label
    return f"This campaign needs at least {campaign.min_followers:,} followers on {platform}. You have {followers:,}."
