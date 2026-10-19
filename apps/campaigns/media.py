"""Photos and videos on a campaign brief.

A brand may attach up to 2 photos, or 1 video, while the campaign is still a Draft. What an upload
really is gets decided here by reading the first bytes of the file, never from the filename or the
Content-Type the browser sent, and the stored name is a random one, so an uploader cannot choose
what ends up on disk or what the server later labels it.
"""
import uuid

from django.db import transaction

from apps.core.exceptions import Conflict
from apps.core.uploads import check_upload

from .models import Campaign, CampaignMedia
from .services import CampaignNotEditable

MAX_PHOTOS = 2
MAX_VIDEOS = 1


class MediaLimitReached(Conflict):
    default_code = "media_limit_reached"
    default_detail = "A campaign can have up to 2 photos or 1 video."


def add_media(campaign: Campaign, upload) -> CampaignMedia:
    """Attach an uploaded photo or video to a Draft campaign, within the 2-photos-or-1-video rule."""
    detected = check_upload(upload)

    with transaction.atomic():
        # Locking the campaign makes two simultaneous uploads count one at a time.
        locked = Campaign.objects.select_for_update().get(pk=campaign.pk)
        if locked.status != Campaign.Status.DRAFT:
            raise CampaignNotEditable("Photos and videos can only be changed while the campaign is a draft.")
        kinds = list(locked.media.values_list("kind", flat=True))
        if detected.kind == CampaignMedia.Kind.VIDEO:
            if kinds:
                raise MediaLimitReached("A video can't be added next to other media. Remove the photos first.")
        else:
            if CampaignMedia.Kind.VIDEO in kinds:
                raise MediaLimitReached("A campaign with a video can't also have photos. Remove the video first.")
            if kinds.count(CampaignMedia.Kind.PHOTO) >= MAX_PHOTOS:
                raise MediaLimitReached("A campaign can have up to 2 photos.")

        media = CampaignMedia(campaign=locked, kind=detected.kind, size=upload.size)
        media.file.save(f"{uuid.uuid4().hex}.{detected.extension}", upload, save=False)
        try:
            media.save()
        except Exception:
            media.file.delete(save=False)  # do not leave an orphan file behind
            raise
    return media


def remove_media(campaign: Campaign, media_id: int) -> bool:
    """Delete one attachment of a Draft campaign. Returns False when it does not exist."""
    with transaction.atomic():
        locked = Campaign.objects.select_for_update().get(pk=campaign.pk)
        if locked.status != Campaign.Status.DRAFT:
            raise CampaignNotEditable("Photos and videos can only be changed while the campaign is a draft.")
        deleted, _ = locked.media.filter(pk=media_id).delete()
    return bool(deleted)
