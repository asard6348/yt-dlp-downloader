#!/usr/bin/env python3

import os
import sys
import shutil
import json
import subprocess


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
    if not os.path.isfile(configs):
        configs = open(configs, 'x').name
    with open(configs, 'w') as c:
        c.write('{\n   "format":"'+frmt+'",\n   "output":"'+outp+'",\n   "metadata":'+str(metadata).lower()+',\n   "ytdlplocate":"'+ytdlploc+'"\n}')


def resolve_yt_dlp(ytdlplocate, cwd, joinp):
    ytdlploc = ytdlplocate
    if ytdlplocate == "lib":
        try:
            import yt_dlp
            ytdlplocate = [sys.executable, "-m", "yt_dlp"]
        except ImportError:
            ytdlplocate = "path"
    
    if ytdlplocate == "path":
        on_path = shutil.which('yt-dlp')
        if on_path:
            ytdlplocate = on_path
        else:
            ytdlplocate = "script"

    if ytdlplocate == "script":
        for candidate in os.listdir(cwd):
            absp = joinp(cwd, candidate)
            if 'yt-dlp' in candidate and os.path.isfile(absp) and os.access(absp, os.X_OK):
                ytdlplocate = absp
                break
        if not os.path.isfile(ytdlplocate) or ytdlplocate == "script":
            raise Exception("yt-dlp could not be found in PATH environment variable, neither in the script current working directory, neither in the user-specified path. Do you have it installed correctly? (https://github.com/yt-dlp/yt-dlp)")

    if not isinstance(ytdlplocate, list): ytdlplocate = [ytdlplocate]
    return ytdlplocate


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


def remove_new_files(output_dir, before):
    after = set(os.listdir(output_dir))
    removed = []
    for name in after - before:
        if not name.endswith(".part"): continue
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
    frmt = "" #Format used to extract downloaded content | Nothing by default uses yt-dlp's default format
    metadata = True #Whether to keep metadata in files by default | True by default
    ytdlplocate = "lib" #Location of yt-dlp | Options: *'lib'*, 'path', 'script', '(YOUR PATH)'
    output = "script" #Location of extraction output | 'script' by default makes 'Output' folder in the current working directory
    configs = "script" #Config file location | 'script' by default makes 'shell-config.json' file in the current working directory

    ytdlploc = ytdlplocate
    outp = output
    joinp = os.path.join
    cwd = os.getcwd()

    configs = joinp(cwd, "shell-config.json") if configs == "script" else configs
    
    cfg_data, newc = fetch_config(configs)
    if cfg_data:
        frmt = cfg_data.get('format', frmt)
        output = cfg_data.get('output', output)
        metadata = cfg_data.get('metadata', metadata)
        ytdlplocate = cfg_data.get('ytdlplocate', ytdlplocate)

    output = joinp(cwd, "Output") if output == "script" else output
    yt_dlp_exe = resolve_yt_dlp(ytdlplocate, cwd, joinp)

    print(f'Using yt-dlp at: {yt_dlp_exe}.')

    while True:
        if newc:
            output = input('Output folder (empty for "Output" next to this script): ')
            if not output or output == "script":
                outp = "script"
                output = joinp(cwd, "Output")
            user_fmt = input('Output format (empty for default): ')
            if user_fmt:
                frmt = user_fmt
            metadata = not input('Embed metadata? (Y/n): ').lower().startswith('n')
            if input('Save settings? (y/N): ').lower().startswith('y'):
                edit_config(configs, frmt, outp, metadata, ytdlploc)
                newc = False
        url = input('URL: ')
        safe_download(url, frmt, output, yt_dlp_exe, metadata)
        print()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        input(f'\x1b[38;2;255;0;0m{e}\x1b[0m')
