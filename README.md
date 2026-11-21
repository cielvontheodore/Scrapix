# Scrapix

TUI downloader for YouTube, Instagram and TikTok. Wraps
[yt-dlp](https://github.com/yt-dlp/yt-dlp) (video, audio) and
[gallery-dl](https://github.com/mikf/gallery-dl) (images).

## Install

```bash
sudo pacman -S ffmpeg        # needed for merge + MP3
uv tool install .            # or: pipx install .
```

## Use

```bash
scrapix                      # saves to ~/Downloads/Scrapix
scrapix -o ~/Videos          # pick another folder
```

Flow: pick site -> pick type -> paste link -> pick video/audio quality -> download.

## Notes

- Public links only for now. Instagram login/cookies not supported yet.
- Download only what you have the right to download.
