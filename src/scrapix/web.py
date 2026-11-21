from __future__ import annotations

import argparse
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_file, send_from_directory
from werkzeug.exceptions import HTTPException

from . import __version__
from . import downloader as dl
from .sites import SITES, detect_site

STATIC = Path(__file__).parent / "static"
MAX_JOBS = 50
DEFAULT_OUTPUT = Path.home() / "Downloads" / "Scrapix"


@dataclass
class Job:
    id: str
    status: str = "queued"  # queued | running | done | error
    done: int = 0
    total: int | None = None
    message: str = ""
    files: list[Path] = field(default_factory=list)

    def public(self) -> dict:
        return {
            "id": self.id,
            "status": self.status,
            "done": self.done,
            "total": self.total,
            "message": self.message,
            "files": [
                {"name": p.name, "size": p.stat().st_size if p.exists() else 0}
                for p in self.files
            ],
        }


def _short(msg: str) -> str:
    msg = msg.replace("ERROR: ", "", 1).strip()
    return msg if len(msg) <= 300 else msg[:297] + "..."


def _int_or_none(value, lo: int, hi: int) -> int | None:
    if value in (None, "", 0, "0"):
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        abort(400, "Nilai kualitas tidak valid")
    if not lo <= n <= hi:
        abort(400, "Nilai kualitas di luar batas")
    return n


def _snapshot(root: Path) -> set[Path]:
    if not root.exists():
        return set()
    return {
        p for p in root.rglob("*")
        if p.is_file() and not any(part.startswith(".scrapix-") for part in p.relative_to(root).parts)
    }


def create_app(
    outdir: Path,
    *,
    allow_any_url: bool = False,
    allowed_hosts: set[str] | None = None,
) -> Flask:
    app = Flask(__name__, static_folder=None)
    jobs: dict[str, Job] = {}
    lock = threading.Lock()
    pool = ThreadPoolExecutor(max_workers=2)

    @app.before_request
    def guard():
        # Block DNS-rebinding: only answer to our own host names.
        if allowed_hosts is not None and request.host not in allowed_hosts:
            abort(403, "Host tidak diizinkan")
        # JSON-only POST: a web page on another site cannot send this cross-origin.
        if request.method == "POST" and not request.is_json:
            abort(415, "Harus JSON")

    @app.errorhandler(HTTPException)
    def on_http_error(e: HTTPException):
        return jsonify(error=e.description or e.name), e.code

    # ---- static (served from root so the service worker can control "/") ----
    @app.get("/")
    def index():
        return send_from_directory(STATIC, "index.html")

    @app.get("/<path:name>")
    def static_root(name: str):
        resp = send_from_directory(STATIC, name)
        if name.endswith(".webmanifest"):
            resp.mimetype = "application/manifest+json"
        if name == "sw.js":
            resp.headers["Cache-Control"] = "no-cache"
        return resp

    # ---- api ----
    @app.get("/api/config")
    def config():
        return jsonify(
            version=__version__,
            sites=[{"key": s.key, "label": s.label, "kinds": list(s.kinds)} for s in SITES],
            audio_bitrates=list(dl.AUDIO_BITRATES),
            video_audio_bitrates=list(dl.VIDEO_AUDIO_BITRATES),
        )

    def clean_url(data) -> str:
        url = str((data or {}).get("url", "")).strip()
        if not url.startswith(("http://", "https://")):
            abort(400, "Link harus diawali http:// atau https://")
        if not allow_any_url and detect_site(url) is None:
            abort(400, "Link harus dari YouTube, Instagram, atau TikTok")
        return url

    @app.post("/api/probe")
    def probe():
        url = clean_url(request.get_json(silent=True))
        try:
            info = dl.probe(url)
        except dl.DownloadFailed as e:
            return jsonify(error=_short(str(e))), 422
        return jsonify(
            title=info.title,
            uploader=info.uploader,
            duration=info.duration,
            heights=info.heights,
        )

    def run_job(job: Job, url: str, kind: str, height: int | None, abr: int | None) -> None:
        job.status = "running"

        def on_progress(done: int, total: int | None) -> None:
            job.done, job.total = done, total

        try:
            if kind == "image":
                before = _snapshot(outdir)
                code = dl.download_images(url, outdir)
                new = sorted(_snapshot(outdir) - before)
                if code != 0 and not new:
                    raise dl.DownloadFailed(
                        f"gallery-dl gagal (kode {code}). Instagram sering butuh login."
                    )
                job.files = new
            else:
                path = dl.download_media(
                    url, outdir, kind=kind, height=height, abr=abr, on_progress=on_progress
                )
                job.files = [path] if path else []
            job.status = "done"
        except dl.DownloadFailed as e:
            job.status, job.message = "error", _short(str(e))
        except Exception as e:  # keep the server alive whatever happens
            job.status, job.message = "error", f"Error tak terduga: {e}"

    @app.post("/api/download")
    def start():
        data = request.get_json(silent=True) or {}
        url = clean_url(data)
        kind = data.get("kind")
        if kind not in ("video", "audio", "image"):
            abort(400, "Jenis download tidak valid")
        height = _int_or_none(data.get("height"), 100, 4320)
        abr = _int_or_none(data.get("abr"), 32, 512)
        job = Job(id=uuid.uuid4().hex[:12])
        with lock:
            jobs[job.id] = job
            while len(jobs) > MAX_JOBS:  # drop the oldest finished job
                old = next((k for k, j in jobs.items() if j.status in ("done", "error")), None)
                if old is None:
                    break
                del jobs[old]
        pool.submit(run_job, job, url, kind, height, abr)
        return jsonify(id=job.id), 202

    def get_job(job_id: str) -> Job:
        job = jobs.get(job_id)
        if job is None:
            abort(404, "Job tidak ditemukan")
        return job

    @app.get("/api/jobs/<job_id>")
    def job_status(job_id: str):
        return jsonify(get_job(job_id).public())

    @app.get("/api/jobs/<job_id>/files/<int:index>")
    def job_file(job_id: str, index: int):
        job = get_job(job_id)
        if not 0 <= index < len(job.files) or not job.files[index].exists():
            abort(404, "File tidak ada")
        return send_file(job.files[index], as_attachment=True)

    return app


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="scrapix-web",
        description="Scrapix web app (installable PWA). Open it in Chrome.",
    )
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT,
                        help="folder tujuan (default: ~/Downloads/Scrapix)")
    parser.add_argument("--host", default="127.0.0.1",
                        help="alamat bind (default 127.0.0.1, hanya perangkat ini)")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv)

    outdir = args.output.expanduser()
    loopback = args.host in ("127.0.0.1", "localhost", "::1")
    allowed = {f"127.0.0.1:{args.port}", f"localhost:{args.port}"} if loopback else None
    if not loopback:
        print("PERINGATAN: server dibuka ke jaringan dan TIDAK punya login. "
              "Siapa pun di jaringan itu bisa memakainya.")

    app = create_app(
        outdir,
        allow_any_url=os.environ.get("SCRAPIX_ALLOW_ANY_URL") == "1",
        allowed_hosts=allowed,
    )
    print(f"Scrapix web: http://localhost:{args.port}   (simpan ke {outdir})")
    app.run(host=args.host, port=args.port, threaded=True)
