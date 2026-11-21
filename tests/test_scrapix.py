from scrapix.downloader import DownloadFailed, _to_media_info, video_format
from scrapix.sites import detect_site

import pytest


def test_detect_site():
    assert detect_site("https://www.youtube.com/watch?v=abc").key == "youtube"
    assert detect_site("https://youtu.be/abc").key == "youtube"
    assert detect_site("https://www.instagram.com/reel/abc/").key == "instagram"
    assert detect_site("https://vm.tiktok.com/abc/").key == "tiktok"
    assert detect_site("https://example.com/x") is None
    assert detect_site("https://notyoutube.com/x") is None


def test_video_format_with_ffmpeg():
    assert video_format(720, 192, True) == (
        "bv*[height<=720]+ba[abr<=192]/bv*[height<=720]+ba/b[height<=720]/b"
    )


def test_video_format_best_and_no_ffmpeg():
    assert video_format(None, None, True) == "bv*+ba/b"
    assert video_format(1080, None, False) == "b[height<=1080]/b"


def test_media_info_heights():
    info = {
        "title": "t",
        "formats": [
            {"height": 360, "vcodec": "avc1"},
            {"height": 1080, "vcodec": "avc1"},
            {"height": 1080, "vcodec": "vp9"},
            {"height": None, "vcodec": "none"},  # audio only
            {"height": 720, "vcodec": "none"},   # not real video
        ],
    }
    assert _to_media_info(info).heights == [1080, 360]


def test_playlist_rejected():
    with pytest.raises(DownloadFailed):
        _to_media_info({"_type": "playlist", "entries": []})
