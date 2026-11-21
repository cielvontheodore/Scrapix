from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class Site:
    key: str
    label: str
    hosts: tuple[str, ...]
    kinds: tuple[str, ...]  # what we can fetch: video, audio, image


SITES: tuple[Site, ...] = (
    Site("youtube", "YouTube", ("youtube.com", "youtu.be"), ("video", "audio")),
    Site("instagram", "Instagram", ("instagram.com",), ("video", "audio", "image")),
    Site("tiktok", "TikTok", ("tiktok.com",), ("video", "audio", "image")),
)


def detect_site(url: str) -> Site | None:
    host = (urlparse(url).hostname or "").lower()
    for site in SITES:
        if any(host == h or host.endswith("." + h) for h in site.hosts):
            return site
    return None
