#!/usr/bin/env python3

import os
import sys
import shutil
import json
import re
import subprocess
import builtins, glob


def fetch_config(configs):
    newcon = False
    data = {}
    try:
        with open(configs) as c:
            data = json.loads(c.read().replace('\\', '/'))
    except FileNotFoundError:
        newcon = True
        pass
    except Exception as e:
        print(f'Config file (shell-config.json) could not be read: {e}')
        newcon = True
        pass
    return data, newcon


resolutions = ["Best", "2160p", "1440p", "1080p", "720p", "480p", "360p", "240p", "144p"]
bitrates = ["Default", "320k", "256k", "192k", "128k", "96k", "64k"]
preset_formats = ["mp3", "aac", "mp4", "mkv"]
audio_formats = ["mp3", "aac", "m4a", "opus", "vorbis", "flac", "wav"]
lossy_audio_formats = ["mp3", "aac", "m4a", "opus", "vorbis"]
recode_formats = ["mov", "avi", "gif"]
time_re = re.compile(r'^(?:\d+:){0,2}\d+(?:\.\d+)?$')


def edit_config(configs, frmt, outp, metadata, ytdlploc, resolution, bitrate):
    os.makedirs(os.path.dirname(configs), exist_ok=True)
    with open(configs, 'w', encoding='utf-8') as c:
        json.dump({'format': frmt, 'output': outp, 'metadata': bool(metadata), 'ytdlplocate': ytdlploc, 'resolution': resolution, 'bitrate': bitrate}, c, indent=4)


def normalize_resolution(value):
    value = str(value).strip().lower()
    if value == "best":
        return "Best"
    if value.isdigit():
        value += "p"
    return value if value in resolutions else None


def normalize_bitrate(value):
    value = str(value).strip().lower()
    if value == "default":
        return "Default"
    if value.isdigit():
        value += "k"
    return value if value in bitrates else None


def ask_choice(prompt, current, normalize, options):
    while True:
        answer = input(prompt)
        if not answer.strip():
            return current
        chosen = normalize(answer)
        if chosen:
            return chosen
        print(f'Unknown value. Options: {", ".join(options)}')


def time_to_seconds(value):
    seconds = 0.0
    for part in value.split(':'):
        seconds = seconds * 60 + float(part)
    return seconds


def validate_trim(start, end):
    for label, value in (("start", start), ("end", end)):
        if value and not time_re.match(value):
            return f'Trim {label} time "{value}" is not valid. Use seconds (90), minutes:seconds (1:30) or hours:minutes:seconds (1:02:03).'
    if start and end and time_to_seconds(end) <= time_to_seconds(start):
        return "Trim end time must be later than the start time."
    return None


def format_args(fmt, options):
    args = []
    if fmt in audio_formats:
        if fmt in preset_formats:
            args += ["-t", fmt]
        else:
            args += ["-x", "--audio-format", fmt]
        if fmt in lossy_audio_formats and options['bitrate'] != "Default":
            args += ["--audio-quality", options['bitrate'].upper()]
    else:
        if fmt in preset_formats:
            args += ["-t", fmt]
        elif fmt in recode_formats:
            args += ["--recode-video", fmt]
        elif fmt and fmt != "webm":
            args += ["-t", fmt]
        if options['resolution'] != "Best":
            height = options['resolution'].rstrip('p')
            args += ["-f", f"bv*[height<={height}]+ba/b[height<={height}]/bv*+ba/b"]
    return args


def trim_args(options):
    start = options['start']
    end = options['end']
    if not start and not end:
        return []
    args = ["--download-sections", f"*{start or '0'}-{end or 'inf'}"]
    if options['precise']:
        args.append("--force-keyframes-at-cuts")
    return args


def resolve_yt_dlp(ytdlplocate, cwd, joinp):
    ytdlploc = ytdlplocate
    message = None
    if ytdlplocate == "lib":
        try:
            import yt_dlp
            ytdlplocate = [sys.executable, "-m", "yt_dlp"]
            message = "Using imported yt-dlp library."
        except ImportError:
            ytdlplocate = "path"
    
    if ytdlplocate == "path":
        on_path = shutil.which('yt-dlp')
        if on_path:
            ytdlplocate = on_path
            message = f"Using yt-dlp on PATH: {on_path}"
        else:
            ytdlplocate = "script"

    if ytdlplocate == "script":
        for candidate in os.listdir(cwd):
            absp = joinp(cwd, candidate)
            if 'yt-dlp' in candidate and os.path.isfile(absp) and os.access(absp, os.X_OK):
                ytdlplocate = absp
                message = f"Using yt-dlp executable nearby: {absp}"
                break
        if not os.path.isfile(ytdlplocate) or ytdlplocate == "script":
            raise Exception("yt-dlp could not be found in PATH environment variable, neither in the script current working directory, neither in the user-specified path. Do you have it installed correctly? (https://github.com/yt-dlp/yt-dlp)")

    if message is None:
        message = f"Using yt-dlp at: {ytdlplocate}"

    if not isinstance(ytdlplocate, list): ytdlplocate = [ytdlplocate]
    return ytdlplocate, message


def download(url, fmt, output_dir, yt_dlp_exe, mtd, options):
    url = url.replace('www.', '')
    args = yt_dlp_exe+[
            '--color', 'always',
            '-P', output_dir
            ]

    args += format_args(fmt, options)
    args += trim_args(options)

    if mtd:
        args.append("-o")
        args.append("%(title)s.%(ext)s")

        args.append("--embed-metadata")

        args.append("--parse-metadata")
        args.append("%(artist,creator,uploader|)s:%(meta_artist)s")

        args.append("--parse-metadata")
        args.append("%(album,playlist_title,playlist|)s:%(meta_album)s")

        args.append("--parse-metadata")
        args.append("%(playlist_index|)s:%(meta_track)s")

    args.append(url)

    result = subprocess.run(args)
    return result.returncode


PARTIAL_RE = re.compile(r'(\.part(-Frag\d+)?|\.ytdl|\.temp)$')


def remove_new_files(output_dir, before):
    after = set(os.listdir(output_dir))
    removed = []
    for name in after - before:
        if not PARTIAL_RE.search(name): continue
        path = os.path.join(output_dir, name)
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
            removed.append(name)
        except OSError:
            pass
    return removed


def safe_download(url, fmt, output_dir, yt_dlp_exe, mtd, options):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    before = set(os.listdir(output_dir))
    try:
        return download(url, fmt, output_dir, yt_dlp_exe, mtd, options)
    except KeyboardInterrupt:
        removed = remove_new_files(output_dir, before)
        for name in removed:
            print(f'Removed: {name}')


def main():
    #CONFIGURATION
    frmt = "" #Format used to extract downloaded content | Nothing by default uses yt-dlp's default format (webm)
    metadata = True #Whether to keep metadata in files by default | True by default
    ytdlplocate = "lib" #Location of yt-dlp | Options: *'lib'*, 'path', 'script', '(YOUR PATH)'
    output = "script" #Location of extraction output | 'script' by default makes 'Output' folder in the current working directory
    configs = "home" #Config file location | 'home' by default points in appdata, .config or library; 'script' in the current working directory
    resolution = "Best"
    bitrate = "Default"

    ytdlploc = ytdlplocate
    outp = output
    joinp = os.path.join
    cwd = os.getcwd()
    cmds = []
    autopath = True
    fileformats = ["webm", "mp4", "mp3", "mkv", "aac", "m4a", "opus", "vorbis", "flac", "wav", "mov", "avi", "gif"]

    if sys.stdin.isatty() and 'idlelib' not in sys.modules:
        if not sys.platform.startswith('win'):
            import readline

            def complete(text, state):
                if autopath:
                    target = os.path.expanduser(text or './')
                    if target.endswith(':'):
                        target += '/'
                    raw = glob.glob(target + '*')
                    options = [m.replace('\\', '/') + ('/' if os.path.isdir(m) else '') for m in raw]
                else:
                    options = [c for c in cmds if c.startswith(text)]
                return options[state] if state < len(options) else None

            readline.set_completer_delims(' \t\n;')
            if 'libedit' in readline.__doc__:
                readline.parse_and_bind('bind ^I rl_complete')
            else:
                readline.parse_and_bind('tab: complete')
            readline.set_completer(complete)
        else:
            import msvcrt

            def win_input(prompt=''):
                sys.stdout.write(prompt)
                sys.stdout.flush()
                buffer = []
                matches, match_idx = [], 0
                tab_base = ''

                while True:
                    ch = msvcrt.getwch()
                    if ch in ('\r', '\n'):
                        print()
                        return ''.join(buffer)
                    elif ch in ('\x00', '\xe0'):
                        msvcrt.getwch()
                    elif ch == '\x08':
                        if buffer:
                            buffer.pop()
                            sys.stdout.write('\b \b')
                            sys.stdout.flush()
                        matches = []
                    elif ch == '\t':
                        if not matches:
                            tab_base = ''.join(buffer)
                            if autopath:
                                target = os.path.expanduser(tab_base or './')
                                if target.endswith(':'):
                                    target += '/'
                                raw = glob.glob(target + '*')
                                matches = [m.replace('\\', '/') + ('/' if os.path.isdir(m) else '') for m in raw]
                            else:
                                matches = [c for c in cmds if c.startswith(tab_base)]
                            match_idx = 0
                        if matches:
                            chosen = matches[match_idx % len(matches)]
                            match_idx += 1
                            sys.stdout.write('\b \b' * len(buffer) + chosen)
                            sys.stdout.flush()
                            buffer = list(chosen)
                            if len(matches) == 1 and chosen != tab_base:
                                matches = []
                    elif ch == '\x03':
                        raise KeyboardInterrupt
                    elif ord(ch) >= 32:
                        buffer.append(ch)
                        sys.stdout.write(ch)
                        sys.stdout.flush()
                        matches = []

            builtins.input = win_input

    APP_DIRNAME = "YtdlpDownloader"
    def default_config_dir():
        home = os.path.expanduser("~")
        if sys.platform.startswith("win"):
            base = os.environ.get("APPDATA") or joinp(home, "AppData", "Roaming")
            return joinp(base, APP_DIRNAME)
        if sys.platform == "darwin":
            return joinp(home, "Library", "Application Support", APP_DIRNAME)
        base = os.environ.get("XDG_CONFIG_HOME") or joinp(home, ".config")
        return joinp(base, "yt-dlp-downloader")

    cfgdir = default_config_dir()
    configs = joinp((cfgdir if configs == "home" else cwd if configs == "script" else configs), "shell-config.json")
    
    cfg_data, newc = fetch_config(configs)
    if cfg_data:
        frmt = cfg_data.get('format', frmt)
        output = cfg_data.get('output', output)
        metadata = cfg_data.get('metadata', metadata)
        if isinstance(metadata, str):
            metadata = metadata.strip().lower() != 'false'
        ytdlplocate = cfg_data.get('ytdlplocate', ytdlplocate)
        ytdlploc = ytdlplocate
        resolution = normalize_resolution(cfg_data.get('resolution', resolution)) or "Best"
        bitrate = normalize_bitrate(cfg_data.get('bitrate', bitrate)) or "Default"

    outp = output
    output = joinp(cwd, "Output") if output == "script" else output
    yt_dlp_exe, startup_msg = resolve_yt_dlp(ytdlplocate, cwd, joinp)

    print(startup_msg)

    urls = []
    prevfmt = None if newc else frmt
    savedc = False

    while True:
        if newc:
            cmds = []
            autopath = True
            output = input('Output folder (empty for "Output" next to this script): ')
            if not output or output == "script":
                outp = "script"
                output = joinp(cwd, "Output")
            else:
                outp = output
            cmds = ['y','n']
            autopath = False
            metadata = not input('Embed metadata? (Y/n): ').lower().startswith('n')
            if input('Save settings? (y/N): ').lower().startswith('y'):
                edit_config(configs, frmt, outp, metadata, ytdlploc, resolution, bitrate)
                savedc = True
            newc = False
        else:
            savedc = True
        cmds = fileformats
        autopath = False
        user_fmt = input('Output format '+('(empty for webm)'if prevfmt is None else f'(empty for {prevfmt if prevfmt else 'webm'})')+': ')
        if not user_fmt:
            user_fmt = "" if prevfmt is None else prevfmt
        prevfmt = user_fmt
        if user_fmt not in audio_formats:
            cmds = resolutions
            resolution = ask_choice(f'Resolution (empty for {resolution}): ', resolution, normalize_resolution, resolutions)
        if user_fmt in lossy_audio_formats:
            cmds = bitrates
            bitrate = ask_choice(f'Audio bitrate (empty for {bitrate}): ', bitrate, normalize_bitrate, bitrates)
        cmds = []
        while True:
            trim_start = input('Trim start (h:m:s, empty for none): ').strip()
            trim_end = input('Trim end (h:m:s, empty for none): ').strip()
            trim_error = validate_trim(trim_start, trim_end)
            if not trim_error:
                break
            print(trim_error)
        precise = False
        if trim_start or trim_end:
            cmds = ['y','n']
            precise = input('Precise cuts? Slower, re-encodes (y/N): ').lower().startswith('y')
        options = {'resolution': resolution, 'bitrate': bitrate, 'start': trim_start, 'end': trim_end, 'precise': precise}
        if savedc:
            edit_config(configs, user_fmt, outp, metadata, ytdlploc, resolution, bitrate)
        cmds = urls
        autopath = False
        url = input('URL: ')
        urls.insert(0, url)
        safe_download(url, user_fmt, output, yt_dlp_exe, metadata, options)
        print()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        input(f'\x1b[38;2;255;0;0m{e}\x1b[0m')
