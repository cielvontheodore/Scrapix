import time

import pytest

from scrapix import downloader as dl
from scrapix.web import create_app


@pytest.fixture
def client(tmp_path):
    return create_app(tmp_path, allow_any_url=True).test_client()


def post(client, path, body):
    return client.post(path, json=body)


def wait_done(client, job_id, timeout=5):
    end = time.time() + timeout
    while time.time() < end:
        j = client.get(f"/api/jobs/{job_id}").get_json()
        if j["status"] in ("done", "error"):
            return j
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def test_pwa_files_served(client):
    assert b"Scrapix" in client.get("/").data
    m = client.get("/manifest.webmanifest")
    assert m.status_code == 200 and m.mimetype == "application/manifest+json"
    sw = client.get("/sw.js")
    assert sw.status_code == 200 and sw.headers["Cache-Control"] == "no-cache"
    assert client.get("/icon-512.png").status_code == 200
    assert client.get("/nope.txt").status_code == 404


def test_config_lists_sites(client):
    cfg = client.get("/api/config").get_json()
    assert [s["key"] for s in cfg["sites"]] == ["youtube", "instagram", "tiktok"]
    assert 320 in cfg["audio_bitrates"]


def test_probe_ok_and_error(client, monkeypatch):
    monkeypatch.setattr(dl, "probe", lambda url: dl.MediaInfo("T", "U", 65, [1080, 720]))
    r = post(client, "/api/probe", {"url": "https://x.test/v"})
    assert r.status_code == 200 and r.get_json()["heights"] == [1080, 720]

    def boom(url):
        raise dl.DownloadFailed("ERROR: nope")

    monkeypatch.setattr(dl, "probe", boom)
    r = post(client, "/api/probe", {"url": "https://x.test/v"})
    assert r.status_code == 422 and r.get_json()["error"] == "nope"


def test_rejects_bad_input(client, tmp_path):
    assert post(client, "/api/probe", {"url": "ftp://x"}).status_code == 400
    assert client.post("/api/probe", data="url=x").status_code == 415
    assert post(client, "/api/download", {"url": "https://x.test", "kind": "zip"}).status_code == 400
    assert post(client, "/api/download", {"url": "https://x.test", "kind": "video", "height": "abc"}).status_code == 400
    strict = create_app(tmp_path).test_client()  # only the 3 supported sites
    assert post(strict, "/api/probe", {"url": "https://example.com/v"}).status_code == 400
    assert post(strict, "/api/probe", {"url": "http://127.0.0.1/x"}).status_code == 400


def test_host_guard(tmp_path):
    app = create_app(tmp_path, allowed_hosts={"localhost:8000"})
    c = app.test_client()
    assert c.get("/", headers={"Host": "evil.test:8000"}).status_code == 403
    assert c.get("/", headers={"Host": "localhost:8000"}).status_code == 200


def test_download_flow(client, tmp_path, monkeypatch):
    def fake(url, outdir, *, kind, height, abr, on_progress):
        on_progress(5, 10)
        f = outdir / "clip.mp4"
        f.write_bytes(b"hello")
        return f

    monkeypatch.setattr(dl, "download_media", fake)
    r = post(client, "/api/download", {"url": "https://x.test/v", "kind": "video", "height": 720, "abr": 128})
    assert r.status_code == 202
    j = wait_done(client, r.get_json()["id"])
    assert j["status"] == "done" and j["files"] == [{"name": "clip.mp4", "size": 5}]
    f = client.get(f"/api/jobs/{j['id']}/files/0")
    assert f.data == b"hello" and "attachment" in f.headers["Content-Disposition"]
    assert client.get(f"/api/jobs/{j['id']}/files/9").status_code == 404
    assert client.get("/api/jobs/unknown").status_code == 404


def test_download_error_is_reported(client, monkeypatch):
    def fail(*a, **k):
        raise dl.DownloadFailed("ERROR: private video")

    monkeypatch.setattr(dl, "download_media", fail)
    r = post(client, "/api/download", {"url": "https://x.test/v", "kind": "audio"})
    j = wait_done(client, r.get_json()["id"])
    assert j["status"] == "error" and j["message"] == "private video"


def test_image_job_collects_new_files(client, tmp_path, monkeypatch):
    def fake_images(url, outdir):
        d = outdir / "instagram" / "user"
        d.mkdir(parents=True)
        (d / "a.jpg").write_bytes(b"1")
        (d / "b.jpg").write_bytes(b"22")
        return 0

    monkeypatch.setattr(dl, "download_images", fake_images)
    r = post(client, "/api/download", {"url": "https://x.test/p", "kind": "image"})
    j = wait_done(client, r.get_json()["id"])
    assert j["status"] == "done" and [f["name"] for f in j["files"]] == ["a.jpg", "b.jpg"]
