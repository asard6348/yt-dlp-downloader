#!/usr/bin/env python3

#CONFIGURATION
fileformats = ["webm", "mkv", "mp4", "aac", "mp3"]
metadata = True #Whether to keep metadata in files by default
ytdlplocate = "path" #Location of yt-dlp. | Options: *'path'*, 'script', '(YOUR PATH)'


import os
import sys
import shutil
import signal
import subprocess
import threading
import tkinter
import tkinter.filedialog
import tkinter.messagebox

joinp = os.path.join

defaultlocation = joinp(os.getcwd(), "Output")


if ytdlplocate == "path":
    on_path = shutil.which('yt-dlp')
    if on_path:
        ytdlplocate = on_path
    else:
        ytdlplocate = "script"
        print("yt-dlp isn't on PATH. Fallbacking to script location.")

if ytdlplocate == "script":
    ytdlplocate = os.path.dirname(os.path.abspath(__file__))
    for candidate in (('yt-dlp.exe', 'yt-dlp_arm64.exe', 'yt-dlp_x86.exe') if os.name == 'nt' else ('yt-dlp', 'yt-dlp_linux', 'yt-dlp_linux_aarch64')):
        local_path = joinp(ytdlplocate, candidate)
        if os.path.isfile(local_path):
            ytdlplocate = local_path
            break
    if not os.path.exists(ytdlplocate):
        print("yt-dlp isn't in the script location.")



def bring_picker(widget):
    location = tkinter.filedialog.askdirectory()
    if location:
        widget.delete(0, tkinter.END)
        widget.insert([0], location)

def download_gui(link, place, formattie, button, interrupt_button, proc_holder):
    if formattie.curselection():
        formattie = [formattie.get(i) for i in formattie.curselection()][0]
    else:
        formattie = fileformats[0]

    url = link.get()
    output_dir = place.get()

    if button:
        button.config(text="Downloading... (see console)", state=tkinter.DISABLED)
    if interrupt_button:
        interrupt_button.pack(expand=True, fill=tkinter.X)

    def worker():
        safe_download(url, formattie, output_dir, ytdlplocate, proc_holder)
        if button:
            button.after(0, lambda: button.config(text="Download", state=tkinter.NORMAL))
        if interrupt_button:
            interrupt_button.after(0, interrupt_button.pack_forget)

    threading.Thread(target=worker, daemon=True).start()

def interrupt_gui(proc_holder):
    proc = proc_holder.get('process')
    if proc is None or proc.poll() is not None:
        print("No active download to interrupt.")
        return

    proc_holder['interrupted'] = True
    try:
        if os.name == 'nt':
            proc.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            proc.send_signal(signal.SIGINT)
        print("Sent interrupt to yt-dlp.")
    except Exception as e:
        print(f"Couldn't interrupt yt-dlp: {e}")

def download(url, fmt, output_dir, yt_dlp_exe, proc_holder):
    url = url.replace('www.', '')
    args = [yt_dlp_exe,
            '--color', 'always',
            '-P', output_dir
            ]

    if not fmt == "webm":
        args.append("-t")
        args.append(fmt)

    if metadata:
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

    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0

    proc = subprocess.Popen(args, creationflags=creationflags)
    proc_holder['process'] = proc
    try:
        result = proc.wait()
    finally:
        proc_holder['process'] = None
    return result


def remove_new_files(output_dir, before):
    after = set(os.listdir(output_dir))
    removed = []
    for name in after - before:
        path = joinp(output_dir, name)
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
            removed.append(name)
        except OSError:
            pass
    return removed


def safe_download(url, fmt, output_dir, yt_dlp_exe, proc_holder):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    before = set(os.listdir(output_dir))
    proc_holder['interrupted'] = False
    try:
        result = download(url, fmt, output_dir, yt_dlp_exe, proc_holder)
    except KeyboardInterrupt:
        result = None
        proc_holder['interrupted'] = True

    if proc_holder.get('interrupted'):
        removed = remove_new_files(output_dir, before)
        for name in removed:
            print(f'Removed: {name}')

    return result


def main():
    root = tkinter.Tk()
    root.title("YouTube Downloader GUI")
    root.resizable(True, False)

    proc_holder = {'process': None, 'interrupted': False}

    tkinter.Label(text="yt-dlp", font=(("Arial", 32))).pack()


    tkinter.Label(text="URL").pack()

    urlthing = tkinter.Entry()
    urlthing.pack(fill=tkinter.X)


    locationframe = tkinter.Frame()

    locationframe.grid_columnconfigure(1, weight=1)
    locationframe.grid_columnconfigure(2, weight=0)

    tkinter.Label(locationframe, text="Output").grid(column=1, columnspan=2, row=0, sticky="WE")

    def textchange(*args):
        txt = outputtext.get()
        outputthing.config(width=max(len(txt)+3, 35))
    
    outputtext = tkinter.StringVar()
    outputtext.trace_add("write", textchange)

    outputthing = tkinter.Entry(locationframe, width=35)#, textvariable=outputtext)
    outputthing.insert([0], defaultlocation)
    outputthing.grid(column=1, row=1, sticky="WE")

    getlocation = tkinter.Button(locationframe, text="Pick", width=5, command=lambda:bring_picker(outputthing))
    getlocation.grid(column=2, row=1, sticky="WE")

    locationframe.pack(fill=tkinter.X)


    tkinter.Label(text="Format").pack()

    formatlist = tkinter.StringVar()
    formatlist.set("\n".join(fileformats))
    formatthing = tkinter.Listbox(root, listvariable=formatlist, height=len(formatlist.get().split("\n")))
    formatthing.pack(fill=tkinter.X)


    metadataframe = tkinter.Frame()

    metadataframe.grid_columnconfigure(1, weight=1)
    metadataframe.grid_columnconfigure(2, weight=1)

    mtdlabel = tkinter.Label(metadataframe, text=f"Embed metadata ({'Yes' if metadata else 'No'})")
    mtdlabel.grid(column=1, columnspan=2, row=0, sticky="WE")

    def ye(*args):
        global metadata; metadata=True; mtdlabel.config(text="Embed metadata (Yes)")
    def nu(*args):
        global metadata; metadata=False; mtdlabel.config(text="Embed metadata (No)")
    tkinter.Button(metadataframe, text="Yes", command=ye).grid(column=1, row=1, sticky="WE")
    tkinter.Button(metadataframe, text="No", command=nu).grid(column=2, row=1, sticky="WE")

    metadataframe.pack(fill=tkinter.X)

    downl = tkinter.Button(text="Download", font=(("Arial", 15, "bold")))
    interr = tkinter.Button(text="Interrupt (Ctrl+C/D in console)", font=(("Arial", 10)))

    downl.config(command=lambda:download_gui(urlthing, outputthing, formatthing, downl, interr, proc_holder))
    interr.config(command=lambda:interrupt_gui(proc_holder))

    downl.pack(expand=True, fill=tkinter.X)

    root.mainloop()




if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nInterrupted.')
    except Exception as e:
        input(f'\x1b[38;2;255;0;0m{e}\x1b[0m')
