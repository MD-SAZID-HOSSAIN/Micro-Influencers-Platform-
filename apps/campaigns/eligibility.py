from .models import Campaign


def is_eligible(campaign: Campaign, followers_by_platform: dict[str, int]) -> bool:
    """Informational only: does the creator have stats for the campaign's platform and enough followers?

    Verified and Unverified stats both count, and the result never blocks applying.
    """
    followers = followers_by_platform.get(campaign.platform)
    if followers is None:
        return False
    return campaign.min_followers is None or followers >= campaign.min_followers
