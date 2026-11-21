"""Real downloads against a local file server. Needs ffmpeg."""
import functools
import http.server
import subprocess
import threading

import pytest

from scrapix import downloader as dl

pytestmark = pytest.mark.skipif(not dl.has_ffmpeg(), reason="ffmpeg not installed")


@pytest.fixture
def sample_url(tmp_path):
    src = tmp_path / "srv"
    src.mkdir()
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=duration=2:size=320x180:rate=15",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-c:v", "libx264", "-c:a", "aac",
         "-shortest", str(src / "sample.mp4")],
        check=True,
    )
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(src))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}/sample.mp4"
    server.shutdown()


def test_video_then_audio_keeps_both(sample_url, tmp_path):
    out = tmp_path / "out"
    seen = []
    video = dl.download_media(sample_url, out, kind="video", abr=128, on_progress=lambda d, t: seen.append(d))
    audio = dl.download_media(sample_url, out, kind="audio", abr=192)
    assert video.exists() and video.suffix == ".mp4"
    assert audio.exists() and audio.suffix == ".mp3"
    assert seen, "progress callback was never called"
    assert sorted(p.name for p in out.iterdir()) == sorted([video.name, audio.name])  # no temp leftovers


def test_audio_twice_does_not_overwrite(sample_url, tmp_path):
    out = tmp_path / "out"
    a = dl.download_media(sample_url, out, kind="audio", abr=128)
    b = dl.download_media(sample_url, out, kind="audio", abr=320)
    assert a != b and a.exists() and b.exists()


def test_bad_link_raises(sample_url, tmp_path):
    with pytest.raises(dl.DownloadFailed):
        dl.probe(sample_url.replace("sample.mp4", "missing.mp4"))
