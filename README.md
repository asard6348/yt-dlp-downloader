# Yt-dlp Downloader

Easy access to yt-dlp, to download videos and audio from thousands of websites.

- `yt-dlp-shell.py` is the shell version, the simplest way to download.
- `yt-dlp-gui.pyw` is the GUI version, with the same options in a window.

## Requirements

**yt-dlp** must be installed. Either install it with `pip install yt-dlp`, add it to your `PATH`, or put the executable next to these scripts. Get it at [github.com/yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp).

**FFmpeg** must be installed for converting, trimming and embedding metadata. Get it at [ffmpeg.org/download.html](https://www.ffmpeg.org/download.html).

The GUI version also needs Python with `tkinter`.

## Options

- **Format:** webm (default), mp4, mkv, mov, avi, gif for video, and mp3, aac, m4a, opus, vorbis, flac, wav for audio. Some formats may need more specific yt-dlp arguments, depending on the site.
- **Resolution:** limits the video quality, from 2160p down to 144p, or `Best`.
- **Audio bitrate:** sets the quality of mp3, aac, m4a, opus and vorbis, from 320k down to 64k.
- **Trim:** download only a part, using a start time, an end time, or both. Times are written as `90`, `1:30` or `1:02:03`. Tick *Precise cuts* (shell: answer `y`) for exact cut points. It is slower.
- **Metadata:** embeds artist, album and track info into the file.

Stopping a download in the middle (for example part of a playlist) only removes the unfinished file. Everything already downloaded stays.

## Settings

Your choices are saved in a config file (`shell-config.json` or `gui-config.json`) in your user settings folder, and the GUI has an *Open config file* button to edit it. Delete the file to start fresh.
