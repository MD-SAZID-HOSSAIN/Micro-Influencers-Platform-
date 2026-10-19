"""Profile pictures: a creator's photo and a brand's logo.

Both work the same way. An upload replaces the previous one; the stored file gets a random name; the
address is mirrored into `photo_url` / `logo_url` so existing readers (directory, campaign cards,
profile completion) need no changes. A link set by hand through the profile API replaces an upload
the same way, so there is only ever one picture.
"""
import uuid

from django.db import transaction

from apps.core.uploads import check_photo

from .models import BrandProfile, CreatorProfile

# profile model -> (file field, the field that mirrors its address)
FIELDS = {
    CreatorProfile: ("photo", "photo_url"),
    BrandProfile: ("logo", "logo_url"),
}


def _forget_file(profile, file_attr: str) -> None:
    """Drop the stored file (after the transaction commits) and empty the field."""
    current = getattr(profile, file_attr)
    if current:
        storage, name = current.storage, current.name
        transaction.on_commit(lambda: storage.delete(name))
    setattr(profile, file_attr, "")


def set_picture(profile, upload):
    """Replace the profile's picture with an uploaded photo (JPG, PNG or WebP)."""
    file_attr, url_attr = FIELDS[type(profile)]
    detected = check_photo(upload)
    with transaction.atomic():
        locked = type(profile).objects.select_for_update().get(pk=profile.pk)
        _forget_file(locked, file_attr)
        getattr(locked, file_attr).save(f"{uuid.uuid4().hex}.{detected.extension}", upload, save=False)
        setattr(locked, url_attr, getattr(locked, file_attr).url)
        locked.save()
    return locked


def clear_picture(profile):
    """Remove the profile's picture, whether it was uploaded or a pasted link."""
    file_attr, url_attr = FIELDS[type(profile)]
    with transaction.atomic():
        locked = type(profile).objects.select_for_update().get(pk=profile.pk)
        _forget_file(locked, file_attr)
        setattr(locked, url_attr, None)
        locked.save()
    return locked


def discard_upload(profile) -> None:
    """A link was set by hand: forget any uploaded file (the caller saves the new link)."""
    file_attr, _ = FIELDS[type(profile)]
    _forget_file(profile, file_attr)
