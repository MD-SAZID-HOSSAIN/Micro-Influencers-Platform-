"""What an uploaded file really is.

Uploads are judged by their first bytes, never by the filename or the Content-Type the browser sent,
and are stored under a random name, so an uploader cannot choose what ends up on disk or how the
server later labels it. Shared by campaign media and profile pictures.
"""
from dataclasses import dataclass

from django.conf import settings

from .exceptions import DomainError

PHOTO = "photo"
VIDEO = "video"


class UnsupportedMedia(DomainError):
    status_code = 400
    default_code = "unsupported_media"
    default_detail = "Upload a JPG, PNG or WebP photo, or an MP4 or WebM video."


class MediaTooLarge(DomainError):
    status_code = 413
    default_code = "media_too_large"
    default_detail = "That file is too large."


@dataclass(frozen=True)
class Detected:
    kind: str
    extension: str


def detect(head: bytes) -> Detected | None:
    """What the file is, judged by its leading bytes. None when it is not a supported type."""
    if head.startswith(b"\xff\xd8\xff"):
        return Detected(PHOTO, "jpg")
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return Detected(PHOTO, "png")
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return Detected(PHOTO, "webp")
    if head[4:8] == b"ftyp":
        return Detected(VIDEO, "mp4")
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        return Detected(VIDEO, "webm")
    return None


def max_bytes(kind: str) -> int:
    return settings.MEDIA_MAX_VIDEO_BYTES if kind == VIDEO else settings.MEDIA_MAX_PHOTO_BYTES


def megabytes(n: int) -> str:
    return f"{n // (1024 * 1024)} MB"


def check_upload(upload) -> Detected:
    """Identify an uploaded file and make sure it is within the size limit for its type."""
    head = upload.read(16)
    upload.seek(0)
    detected = detect(head)
    if detected is None:
        raise UnsupportedMedia()
    limit = max_bytes(detected.kind)
    if upload.size > limit:
        raise MediaTooLarge(f"A {detected.kind} can be at most {megabytes(limit)}.")
    return detected


def check_photo(upload) -> Detected:
    """Like ``check_upload`` but only photos are acceptable (profile pictures and logos)."""
    head = upload.read(16)
    upload.seek(0)
    detected = detect(head)
    if detected is None or detected.kind != PHOTO:
        raise UnsupportedMedia("Upload a JPG, PNG or WebP photo.")
    return check_upload(upload)
