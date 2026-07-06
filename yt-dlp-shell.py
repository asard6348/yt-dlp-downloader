#!/usr/bin/env python3
import os
import sys
import shutil
import argparse
import subprocess


def get_script_dir():
    return os.getcwd()


def get_output_dir():
    output_dir = os.path.join(get_script_dir(), 'Output')
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def resolve_yt_dlp():
    on_path = shutil.which('yt-dlp')
    if on_path:
        return on_path

    script_dir = get_script_dir()
    for candidate in (('yt-dlp.exe', 'yt-dlp_arm64.exe', 'yt-dlp_x86.exe') if os.name == 'nt' else ('yt-dlp', 'yt-dlp_linux', 'yt-dlp_linux_aarch64')):
        local_path = os.path.join(script_dir, candidate)
        if os.path.isfile(local_path):
            return local_path

    raise FileNotFoundError(
        f"yt-dlp isn't on PATH, and no yt-dlp.exe was found next to this script ({script_dir})."
    )


def download(url, fmt, output_dir, yt_dlp_exe):
    args = [
        yt_dlp_exe,
        '--color', 'always',
        '-P', output_dir,
        '-o', '%(title)s.%(ext)s',
        '-t', fmt,
        '--embed-metadata',
        '--parse-metadata', '%(artist,creator,uploader)s:%(meta_artist)s',
        '--parse-metadata', '%(album,playlist_title,playlist)s:%(meta_album)s',
        '--parse-metadata', '%(playlist_index)s:%(meta_track)s',
        url,
    ]
    result = subprocess.run(args)
    return result.returncode


def remove_new_files(output_dir, before):
    after = set(os.listdir(output_dir))
    removed = []
    for name in after - before:
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


def safe_download(url, fmt, output_dir, yt_dlp_exe):
    before = set(os.listdir(output_dir))
    try:
        return download(url, fmt, output_dir, yt_dlp_exe)
    except KeyboardInterrupt:
        removed = remove_new_files(output_dir, before)
        for name in removed:
            print(f'Removed: {name}')


def main():
    parser = argparse.ArgumentParser(description='Download & tag audio with yt-dlp.')
    parser.add_argument('format', nargs='?')
    parser.add_argument('url', nargs='?')
    cli_args = parser.parse_args()

    output_dir = get_output_dir()
    yt_dlp_exe = resolve_yt_dlp()
    print(f'Output folder: {output_dir}')
    print(f'Using yt-dlp: {yt_dlp_exe}')

    if cli_args.format and cli_args.url:
        sys.exit(safe_download(cli_args.url, cli_args.format, output_dir, yt_dlp_exe))

    while True:
        fmt = input('Output format: ')
        url = input('URL: ')
        safe_download(url, fmt, output_dir, yt_dlp_exe)
        print()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nInterrupted.')
    except Exception as e:
        input(f'\x1b[38;2;255;0;0m{e}\x1b[0m')
