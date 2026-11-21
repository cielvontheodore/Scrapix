from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import yt_dlp
from yt_dlp.utils import DownloadError

AUDIO_BITRATES = (320, 192, 128)
VIDEO_AUDIO_BITRATES = (192, 128)

# on_progress(downloaded_bytes, total_bytes_or_None)
ProgressFn = Callable[[int, "int | None"], None]


class _QuietLogger:
    """Stop yt-dlp from printing over our own UI."""

    def debug(self, msg): pass
    def info(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): pass


class DownloadFailed(Exception):
    """Any error we want to show to the user as plain text."""


@dataclass
class MediaInfo:
    title: str
    uploader: str | None
    duration: int | None
    heights: list[int]  # available video heights, high to low


def has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def _to_media_info(info: dict) -> MediaInfo:
    if info.get("_type") == "playlist":
        raise DownloadFailed("Link playlist belum didukung. Pakai link satu video.")
    heights = sorted(
        {
            f["height"]
            for f in info.get("formats") or []
            if f.get("height") and f.get("vcodec") != "none"
        },
        reverse=True,
    )
    return MediaInfo(
        title=info.get("title") or "untitled",
        uploader=info.get("uploader"),
        duration=info.get("duration"),
        heights=heights,
    )


def probe(url: str) -> MediaInfo:
    """Read info about the link without downloading anything."""
    opts = {"logger": _QuietLogger(), "noplaylist": True, "skip_download": True}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except DownloadError as e:
        raise DownloadFailed(str(e)) from e
    return _to_media_info(info)


def video_format(height: int | None, abr: int | None, ffmpeg: bool) -> str:
    h = f"[height<={height}]" if height else ""
    a = f"[abr<={abr}]" if abr else ""
    if ffmpeg:
        parts = [f"bv*{h}+ba{a}", f"bv*{h}+ba", f"b{h}", "b"]
    else:
        parts = [f"b{h}", "b"]
    return "/".join(dict.fromkeys(parts))  # drop duplicates, keep order


def download_media(
    url: str,
    outdir: Path,
    *,
    kind: str,
    height: int | None = None,
    abr: int | None = None,
    on_progress: ProgressFn | None = None,
) -> Path | None:
    """Download video (kind="video") or MP3 audio (kind="audio")."""
    outdir.mkdir(parents=True, exist_ok=True)
    ffmpeg = has_ffmpeg()
    if kind == "audio" and not ffmpeg:
        raise DownloadFailed("Audio MP3 butuh ffmpeg. Arch/CachyOS: sudo pacman -S ffmpeg")

    # Audio is extracted in a private temp folder. yt-dlp deletes the source file
    # after extraction, and that source can share its name with a video the user
    # already downloaded.
    work = Path(tempfile.mkdtemp(prefix=".scrapix-", dir=outdir)) if kind == "audio" else outdir

    def hook(d: dict) -> None:
        if on_progress and d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            on_progress(d.get("downloaded_bytes") or 0, total)

    opts: dict = {
        "outtmpl": str(work / "%(title).150B [%(id)s].%(ext)s"),
        "noplaylist": True,
        "logger": _QuietLogger(),
        "noprogress": True,
        "progress_hooks": [hook],
    }
    if kind == "audio":
        q = abr or AUDIO_BITRATES[0]
        opts["format"] = f"ba[abr<={q}]/ba/b"
        opts["postprocessors"] = [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": str(q)}
        ]
    else:
        opts["format"] = video_format(height, abr, ffmpeg)
        if ffmpeg:
            opts["merge_output_format"] = "mp4"

    try:
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
        except DownloadError as e:
            raise DownloadFailed(str(e)) from e

        done = (info or {}).get("requested_downloads") or []
        path = Path(done[0]["filepath"]) if done and done[0].get("filepath") else None
        if kind == "audio" and path is not None:
            path = _move_unique(path, outdir)
        return path
    finally:
        if work != outdir:
            shutil.rmtree(work, ignore_errors=True)


def _move_unique(src: Path, dest_dir: Path) -> Path:
    """Move src into dest_dir without overwriting: name.mp3, name (1).mp3, ..."""
    target = dest_dir / src.name
    n = 1
    while target.exists():
        target = dest_dir / f"{src.stem} ({n}){src.suffix}"
        n += 1
    shutil.move(str(src), str(target))
    return target


def download_images(url: str, outdir: Path) -> int:
    """Download pictures with gallery-dl. Returns its status code (0 = ok)."""
    from gallery_dl import config, job

    outdir.mkdir(parents=True, exist_ok=True)
    config.clear()
    config.load()
    config.set(("extractor",), "base-directory", str(outdir))
    return job.DownloadJob(url).run()
