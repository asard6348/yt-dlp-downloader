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


def edit_config(configs, frmt, outp, metadata, ytdlploc):
    with open(configs, 'w', encoding='utf-8') as c:
        json.dump({'format': frmt, 'output': outp, 'metadata': bool(metadata), 'ytdlplocate': ytdlploc}, c, indent=4)


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


def download(url, fmt, output_dir, yt_dlp_exe, mtd):
    url = url.replace('www.', '')
    args = yt_dlp_exe+[
            '--color', 'always',
            '-P', output_dir
            ]

    if fmt:
        args.append("-t")
        args.append(fmt)

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


def safe_download(url, fmt, output_dir, yt_dlp_exe, mtd):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    before = set(os.listdir(output_dir))
    try:
        return download(url, fmt, output_dir, yt_dlp_exe, mtd)
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
    configs = "script" #Config file location | 'script' by default makes 'shell-config.json' file in the current working directory

    ytdlploc = ytdlplocate
    outp = output
    joinp = os.path.join
    cwd = os.getcwd()
    cmds = []
    autopath = True
    fileformats = ["webm", "mp4", "mp3", "mkv", "aac"]

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

    configs = joinp(cwd, "shell-config.json") if configs == "script" else configs
    
    cfg_data, newc = fetch_config(configs)
    if cfg_data:
        frmt = cfg_data.get('format', frmt)
        output = cfg_data.get('output', output)
        metadata = cfg_data.get('metadata', metadata)
        if isinstance(metadata, str):
            metadata = metadata.strip().lower() != 'false'
        ytdlplocate = cfg_data.get('ytdlplocate', ytdlplocate)
        ytdlploc = ytdlplocate

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
                edit_config(configs, frmt, outp, metadata, ytdlploc)
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
        if savedc:
            edit_config(configs, user_fmt, outp, metadata, ytdlploc)
        cmds = urls
        autopath = False
        url = input('URL: ')
        urls.insert(0, url)
        safe_download(url, user_fmt, output, yt_dlp_exe, metadata)
        print()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        input(f'\x1b[38;2;255;0;0m{e}\x1b[0m')
