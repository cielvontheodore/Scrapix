# Scrapix

Downloader for YouTube, Instagram and TikTok. Wraps
[yt-dlp](https://github.com/yt-dlp/yt-dlp) (video, audio) and
[gallery-dl](https://github.com/mikf/gallery-dl) (images).

Two ways to use it:

- `scrapix`: terminal menu (TUI)
- `scrapix-web`: small local web app you can install from Chrome (PWA)

## Install

```bash
sudo pacman -S ffmpeg        # needed for merge + MP3 (Termux: pkg install ffmpeg)
uv tool install .            # or: pipx install .   (Termux: pip install .)
```

## Terminal (TUI)

```bash
scrapix                      # saves to ~/Downloads/Scrapix
scrapix -o ~/Videos          # pick another folder
```

Flow: pick site -> pick type -> paste link -> pick video/audio quality -> download.

## Web app (PWA)

```bash
scrapix-web                  # then open http://localhost:8000 in Chrome
scrapix-web --port 9000 -o ~/Videos
```

In Chrome, use the "Install app" button (or the browser menu) to add it to the home
screen. The server only listens on `127.0.0.1` by default and has no login, so do not
expose it with `--host 0.0.0.0` on a network you do not trust.

On Termux, run `termux-setup-storage` once and use
`scrapix-web -o ~/storage/downloads/Scrapix` so files show up in the gallery.

## Notes

- Public links only for now. Instagram posts usually need a login: put your browser
  cookies in gallery-dl's config (`~/.config/gallery-dl/config.json`, key
  `extractor.instagram.cookies`). On Termux use a `cookies.txt` file path.
- Download only what you have the right to download.

## Tests

```bash
pip install -e ".[dev]" && pytest
```
