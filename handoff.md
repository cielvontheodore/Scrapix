# Scrapix handoff

Last updated: 2026-11-21. Project version in the zip: **0.2.0**.

## Goal

All-in-one downloader for YouTube, Instagram and TikTok (video, audio-only, pictures).
End goal: runs **fully on the user's own Android phone**, no outside server, and no
Termux for the end user (the user thinks Termux needs too much technical skill).

## Repo and where things are

- GitHub: `cielvontheodore/Scrapix` (branch `main`). Readable through the Graphify MCP
  (`list_repositories`, then `graphify_rank_files` and friends). Last index seen was commit `cc854c2`,
  which is **v0.1.0 (TUI only)**.
- `scrapix.zip` (v0.2.0) was handed to the user in chat. It adds the web app. It is **not
  confirmed pushed** to GitHub yet, so the repo may still be on v0.1.0.
- User machine: CachyOS (Arch), zsh, uses `uv`. Also wants to run it on Android.

## Decisions already made (do not re-litigate)

1. **Wrapper, not scrapers.** Use yt-dlp (video/audio) and gallery-dl (images).
2. **Python.** Import yt-dlp and gallery-dl as libraries, no shelling out.
3. **TUI** with `questionary` + `rich` (Textual maybe later). Name: **Scrapix**.
4. **Phone version = PWA with Flask backend** (installable from Chrome), not FastAPI:
   pydantic's Rust build is painful on Termux.
5. **Step 2 plan = Android APK** that embeds Python (Chaquopy) and shows the same web UI in a
   WebView against a Flask server on localhost. Step 1 work is the app's contents.

## What exists (v0.2.0)

```
pyproject.toml            hatchling, src layout, scripts: scrapix, scrapix-web
src/scrapix/
  sites.py                Site list (YouTube, Instagram, TikTok) + detect_site(url)
  downloader.py           probe(), download_media(), download_images(), video_format(), DownloadFailed
  ui.py / cli.py          TUI flow + argparse (-o/--output)
  web.py                  Flask app: create_app(), main() for scrapix-web
  static/                 index.html (single page, Indonesian UI), manifest.webmanifest, sw.js, 3 icons
tests/                    test_scrapix.py, test_web.py, test_download_e2e.py (needs ffmpeg)
```

Flow (TUI and web): pick site -> pick type -> paste link -> probe (yt-dlp, no download) ->
pick video height + audio bitrate -> download with progress. Images skip the probe.

Web API: `GET /api/config`, `POST /api/probe`, `POST /api/download` (returns job id),
`GET /api/jobs/<id>`, `GET /api/jobs/<id>/files/<n>`. Jobs run in a 2-worker thread pool,
in memory, max 50 kept.

Safety choices in `web.py`: binds `127.0.0.1` by default, Host-header allowlist (anti DNS
rebinding), POST must be JSON, URLs limited to the 3 sites unless env
`SCRAPIX_ALLOW_ANY_URL=1` (used for local tests only), no login.

## Tested vs not tested

Tested (sandbox, local file server + ffmpeg, 16 tests pass):
- probe, video download, MP3 download, progress callback, bad-link error.
- Flask routes, job flow, file download, host guard, input rejection.
- Interactive TUI driven through a pty (v0.1.0 flow).
- Wheel contains the static files.

**Not tested:**
- Real YouTube / Instagram / TikTok links (sandbox has no access to them).
- Real gallery-dl image download (only that the API can be called).
- The web UI in a real browser, and the Chrome "Install app" prompt (`beforeinstallprompt`).
- Anything on Termux or Android.

## Known issues and gaps

- **Instagram needs login.** The user hit `401 Unauthorized` (gallery-dl exit code 4) on a
  public photo post. Workaround given: gallery-dl config
  `~/.config/gallery-dl/config.json` with `extractor.instagram.cookies: ["firefox"]`.
  On Termux the browser-cookie route does not work; use a `cookies.txt` file path.
  Not built into Scrapix yet.
- Playlist links are rejected on purpose (single video only).
- Video + audio are two streams, so the progress bar resets once during video downloads.
- Image jobs find their files by diffing the output folder before/after. Two image jobs
  running at the same time can mix their file lists.
- Default output is `~/Downloads/Scrapix`; on Termux it should be `~/storage/downloads/Scrapix`
  (needs `termux-setup-storage`). No auto-detect yet.
- Newer yt-dlp may want a JS runtime for YouTube (unverified). If YouTube errors mention it,
  try `nodejs`/`deno`.
- A bug was found and fixed this session: audio extraction deleted a same-named video file.
  Audio now goes through a temp folder `.scrapix-*` inside the output dir and is moved out
  without overwriting.

## Next steps (suggested order)

1. User pushes v0.2.0, runs `scrapix-web`, opens `http://localhost:8000` in Chrome, checks
   layout on a phone, and reports real-link errors.
2. Add Instagram cookies support (`--cookies` option or a field in the web UI).
3. Termux niceties: detect Termux and default to `~/storage/downloads/Scrapix`.
4. Step 2, the APK:
   - Android project with Chaquopy, a WebView, Python starting Flask on localhost.
   - **ffmpeg must be bundled** (arm64 binary shipped as a native lib so Android lets it
     execute). This is the hardest part.
   - The sandbox has no Android SDK, so the user builds it (Android Studio) or we write a
     GitHub Actions workflow.
   - WebView needs a download listener for the `/files/<n>` links.
   - Google Play will most likely reject a YouTube downloader. Distribute via GitHub
     releases or F-Droid.
5. Existing apps that already do the video part: Seal and YTDLnis. Scrapix is only worth it
   for the custom flow.

## Working notes for the next session

- The user writes Indonesian mixed with English and asked for **"caveman mode"** (short,
  blunt sentences, small words). Reply in Indonesian, keep it short.
- Be honest about what is untested. Say it when a result comes from a sandbox that cannot reach
  the real sites.
- In the sandbox bash tool, do not `pkill -f <name>` when that name appears in the same
  command line: it kills the shell. Save PIDs with `$!` and `kill` them.
