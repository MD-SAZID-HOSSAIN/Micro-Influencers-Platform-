import json
import logging
import re
import urllib.request
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def parse_subscriber_count(text: str) -> int:
    if not text:
        return 0
    cleaned = text.strip()
    m = re.search(r"([\d\.]+)\s*([KMBkmb])?\s*subscribers?", cleaned, re.I)
    if not m:
        m2 = re.search(r"([\d\.]+)\s*([KMBkmb])?", cleaned)
        if not m2:
            return 0
        num_str, unit = m2.group(1), m2.group(2)
    else:
        num_str, unit = m.group(1), m.group(2)

    try:
        val = float(num_str)
    except ValueError:
        return 0

    if unit:
        u = unit.upper()
        if u == "K":
            val *= 1_000
        elif u == "M":
            val *= 1_000_000
        elif u == "B":
            val *= 1_000_000_000
    return int(val)


def normalize_youtube_input(handle_or_url: str) -> tuple[str, str]:
    """Return (normalized_fetch_url, clean_handle).

    Handles:
    - '@rajonahmed'
    - 'rajonahmed'
    - 'https://www.youtube.com/@rajonahmed'
    - 'youtube.com/@rajonahmed'
    - 'www.youtube.com/@rajonahmed'
    - 'https://www.youtube.com/@www.youtube.com/@rajonahmed'
    - 'https://www.youtube.com/channel/UC...'
    """
    raw = (handle_or_url or "").strip().strip("\"' ")
    if not raw:
        return "", ""

    # If it contains an '@', extract the handle from after the last '@'
    if "@" in raw:
        handle_part = raw.split("@")[-1].strip().split("/")[0].split("?")[0]
        clean_handle = f"@{handle_part}"
        return f"https://www.youtube.com/{clean_handle}", clean_handle

    if "channel/" in raw:
        cid = raw.split("channel/")[-1].strip().split("/")[0].split("?")[0]
        return f"https://www.youtube.com/channel/{cid}", cid

    if not (raw.startswith("http://") or raw.startswith("https://")):
        raw = raw.replace("www.youtube.com/", "").replace("youtube.com/", "").strip("/")
        return f"https://www.youtube.com/@{raw}", f"@{raw}"

    parsed = urlparse(raw)
    path = parsed.path.rstrip("/")
    clean_url = f"https://www.youtube.com{path}" if path else raw
    handle = clean_url.split("/")[-1]
    if not handle.startswith("@"):
        handle = f"@{handle}"

    return clean_url, handle


def fetch_public_channel(handle_or_url: str) -> dict:
    """Fetch live channel data directly from YouTube's public page."""
    fetch_url, handle = normalize_youtube_input(handle_or_url)
    if not fetch_url:
        return {
            "title": "",
            "handle": "",
            "canonical_url": "",
            "subscribers": 0,
            "videos_count": 0,
            "avatar_url": "",
            "success": False,
        }

    try:
        req = urllib.request.Request(
            fetch_url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        m = re.search(r"var ytInitialData\s*=\s*({.*?});</script>", html)
        data = json.loads(m.group(1)) if m else {}

        meta = data.get("metadata", {}).get("channelMetadataRenderer", {})
        title = meta.get("title", "") or handle.lstrip("@")
        canonical_url = meta.get("ownerUrls", [fetch_url])[0] if meta.get("ownerUrls") else fetch_url
        if canonical_url.startswith("http://"):
            canonical_url = f"https://{canonical_url[7:]}"

        avatar_url = ""
        if meta.get("avatar", {}).get("thumbnails"):
            avatar_url = meta["avatar"]["thumbnails"][-1]["url"]

        sub_count_text = ""
        video_count_text = ""
        header_vm = (
            data.get("header", {})
            .get("pageHeaderRenderer", {})
            .get("content", {})
            .get("pageHeaderViewModel", {})
        )
        rows = (
            header_vm.get("metadata", {})
            .get("contentMetadataViewModel", {})
            .get("metadataRows", [])
        )
        for row in rows:
            for part in row.get("metadataParts", []):
                text = part.get("text", {}).get("content", "")
                if "subscriber" in text.lower():
                    sub_count_text = text
                elif "video" in text.lower():
                    video_count_text = text

        if not sub_count_text:
            sub_m = re.search(r"([0-9\.]+[KMB]?\s+subscribers?)", html, re.I)
            if sub_m:
                sub_count_text = sub_m.group(1)

        subs = parse_subscriber_count(sub_count_text)

        videos_count = 0
        if video_count_text:
            v_m = re.search(r"([\d,]+)\s+videos?", video_count_text, re.I)
            if v_m:
                videos_count = int(v_m.group(1).replace(",", ""))

        if "/@" in canonical_url:
            handle = f"@{canonical_url.split('/@')[-1]}"

        return {
            "title": title,
            "handle": handle,
            "canonical_url": canonical_url,
            "subscribers": subs,
            "subscriber_text": sub_count_text or f"{subs} subscribers",
            "videos_count": videos_count,
            "avatar_url": avatar_url,
            "success": True,
        }
    except Exception as exc:
        logger.warning("Could not fetch YouTube channel live for %s: %s", handle_or_url, exc)
        return {
            "title": handle.lstrip("@"),
            "handle": handle,
            "canonical_url": fetch_url,
            "subscribers": 0,
            "videos_count": 0,
            "avatar_url": "",
            "success": False,
            "error": str(exc),
        }
