from __future__ import annotations

from pathlib import Path

import questionary
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from . import downloader as dl
from .sites import SITES, Site, detect_site

console = Console()

KIND_LABELS = {
    "video": "Video penuh",
    "audio": "Audio saja (MP3)",
    "image": "Gambar / foto",
}


class Cancelled(Exception):
    """User pressed Ctrl+C in a prompt."""


def _ask(question):
    answer = question.ask()
    if answer is None:
        raise Cancelled
    return answer


def pick_site() -> Site:
    return _ask(
        questionary.select(
            "Mau ambil dari mana?",
            choices=[questionary.Choice(s.label, value=s) for s in SITES],
        )
    )


def pick_kind(site: Site) -> str:
    return _ask(
        questionary.select(
            "Mau download apa?",
            choices=[questionary.Choice(KIND_LABELS[k], value=k) for k in site.kinds],
        )
    )


def ask_url(site: Site) -> str:
    def valid(v: str):
        if v.strip().startswith(("http://", "https://")):
            return True
        return "Link harus diawali http:// atau https://"

    url = _ask(questionary.text("Tempel link:", validate=valid)).strip()
    found = detect_site(url)
    if found is None or found.key != site.key:
        console.print(f"[yellow]Link ini sepertinya bukan {site.label}. Lanjut saja.[/]")
    return url


def pick_height(info: dl.MediaInfo) -> int | None:
    if not info.heights:
        return None
    choices = [questionary.Choice("Terbaik", value=0)]
    choices += [questionary.Choice(f"{h}p", value=h) for h in info.heights]
    return _ask(questionary.select("Kualitas video:", choices=choices)) or None


def pick_audio(bitrates: tuple[int, ...], with_best: bool) -> int | None:
    choices = [questionary.Choice("Terbaik", value=0)] if with_best else []
    choices += [questionary.Choice(f"{b} kbps", value=b) for b in bitrates]
    return _ask(questionary.select("Kualitas audio:", choices=choices)) or None


def _fmt_duration(seconds: int | None) -> str:
    if not seconds:
        return "?"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _with_progress(fn):
    columns = (
        TextColumn("[bold]Download"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
    )
    with Progress(*columns, console=console) as progress:
        task = progress.add_task("dl", total=None)

        def on_progress(done: int, total: int | None) -> None:
            progress.update(task, completed=done, total=total)

        return fn(on_progress)


def run_flow(outdir: Path) -> None:
    site = pick_site()
    kind = pick_kind(site)
    url = ask_url(site)

    if kind == "image":
        console.print("[dim]Mengambil gambar...[/]")
        code = dl.download_images(url, outdir)
        if code == 0:
            console.print(f"[green]Selesai.[/] Gambar ada di {outdir}")
        else:
            console.print(f"[red]Gagal.[/] gallery-dl kode {code}")
        return

    with console.status("Cek info link..."):
        info = dl.probe(url)
    console.print(
        Panel(
            f"[bold]{info.title}[/]\n{info.uploader or '-'}  |  {_fmt_duration(info.duration)}",
            expand=False,
        )
    )

    if kind == "video":
        height = pick_height(info)
        abr = pick_audio(dl.VIDEO_AUDIO_BITRATES, with_best=True)
    else:
        height = None
        abr = pick_audio(dl.AUDIO_BITRATES, with_best=False)

    if kind == "video" and not dl.has_ffmpeg():
        console.print(
            "[yellow]ffmpeg tidak ketemu. Video+audio tidak bisa digabung, "
            "dan pilihan kualitas bisa kurang tepat. "
            "Arch/CachyOS: sudo pacman -S ffmpeg[/]"
        )

    path = _with_progress(
        lambda cb: dl.download_media(
            url, outdir, kind=kind, height=height, abr=abr, on_progress=cb
        )
    )
    console.print(f"[green]Selesai.[/] {path or outdir}")


def run(outdir: Path) -> int:
    console.print(Panel("[bold]Scrapix[/]  YouTube, Instagram, TikTok", expand=False))
    try:
        while True:
            try:
                run_flow(outdir)
            except dl.DownloadFailed as e:
                console.print(f"[red]Gagal:[/] {e}")
            if not _ask(questionary.confirm("Download lagi?", default=True)):
                return 0
    except (Cancelled, KeyboardInterrupt):
        console.print("\n[dim]Dibatalkan.[/]")
        return 130
