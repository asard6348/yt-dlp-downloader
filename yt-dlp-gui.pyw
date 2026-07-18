#!/usr/bin/env python3

#CONFIGURATION
fileformats = ["webm", "mkv", "aac", "mp4", "mp3"] #Default formats sequence
metadata = True #Whether to keep metadata in files by default
ytdlplocate = "path" #Location of yt-dlp. | Options: *'path'*, 'script', '(YOUR PATH)'
output = "script" #Location of extraction output | 'script' by default makes 'Output' folder in the current working directory


import os
import io
import sys
import shutil
import json
import signal
import subprocess
import threading
import tkinter
import tkinter.filedialog
import tkinter.messagebox
import tkinter.ttk

if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')

joinp = os.path.join
cwd = os.getcwd()


configs = joinp(cwd, "gui-config.json")

if not os.path.isfile(configs):
    configs = open(configs, 'x').name
    with open(configs, 'w') as c:
        c.write('{\n   "format":"'+fileformats[0]+'",\n   "output":"'+output+'",\n   "metadata":'+str(metadata).lower()+',\n   "ytdlplocate":"'+ytdlplocate+'"\n}')

try:
    with open(configs) as c:
        jsconfig = json.loads(c.read().replace('\\', '/'))
        fileformats.insert(0, fileformats.pop(fileformats.index(jsconfig['format'])))
        output = jsconfig['output']
        metadata = jsconfig['metadata']
        ytdlplocate = jsconfig['ytdlplocate']
except Exception as e:
    print(e)
    pass


defaultlocation = joinp(cwd, "Output") if output == "script" else output

ANSI_BASE_HEX = ['#000000', '#cd0000', '#00cd00', '#cdcd00', '#5c9fd4', '#cd00cd', '#00cdcd', '#e5e5e5']
ANSI_BRIGHT_HEX = ['#7f7f7f', '#ff5555', '#55ff55', '#ffff55', '#5555ff', '#ff55ff', '#55ffff', '#ffffff']


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

def setup_ansi_tags(text):
    for i in range(8):
        text.tag_configure(f'fg{i}', foreground=ANSI_BASE_HEX[i])
        text.tag_configure(f'fg{i}b', foreground=ANSI_BRIGHT_HEX[i])
    text.tag_configure('fgdefaultb', foreground='#ffffff')

def ansi_tag(fg, bold):
    if fg is None:
        return 'fgdefaultb' if bold else None
    return f'fg{fg}b' if bold else f'fg{fg}'

def sgr_apply(params, fg, bold):
    codes = [int(p) if p else 0 for p in params.split(';')] if params else [0]
    for code in codes:
        if code == 0:
            fg, bold = None, False
        elif code == 1:
            bold = True
        elif code == 22:
            bold = False
        elif 30 <= code <= 37:
            fg = code - 30
        elif code == 39:
            fg = None
        elif 90 <= code <= 97:
            fg = code - 90
            bold = True
    return fg, bold

def open_console_window(proc_holder, edit=False):
    console = {}

    win = tkinter.Toplevel()
    win.title("yt-dlp output")
    win.geometry("700x400")

    def on_close(console):
        if console['button'].cget('text') != "Close":
            close = tkinter.messagebox.askyesno(title="Youtube Downloader - Cancelation", message="Would you like to interrupt this process?" if not edit else "Would you like to discard changes?")
            if close:
                if edit:
                    win.destroy()
                else:
                    interrupt_gui(proc_holder, console)
        else:
            win.destroy()
    
    win.protocol("WM_DELETE_WINDOW", lambda:on_close(console))
    
    if edit:
        button = tkinter.Button(win, text="Close")
    else:
        button = tkinter.Button(win, text="Interrupt", command=lambda:interrupt_gui(proc_holder, console))
    button.pack(side=tkinter.BOTTOM, fill=tkinter.X)

    scrollbar = tkinter.Scrollbar(win)
    scrollbar.pack(side=tkinter.RIGHT, fill=tkinter.Y)

    if edit:
        text = tkinter.Text(win, wrap=tkinter.NONE, font="TkFixedFont", yscrollcommand=scrollbar.set)
    else:
        text = tkinter.Text(win, state=tkinter.DISABLED, bg="black", fg="white", wrap=tkinter.NONE, font="TkFixedFont", yscrollcommand=scrollbar.set)
    text.pack(side=tkinter.LEFT, fill=tkinter.BOTH, expand=True)
    scrollbar.config(command=text.yview)

    if not edit: setup_ansi_tags(text)

    win.lift()

    console['window'] = win
    console['text'] = text
    console['button'] = button
    return console

def console_append(text, segments):
    text.config(state=tkinter.NORMAL)
    text.delete("end-1c linestart", "end-1c")
    for tag, s in segments:
        text.insert("end-1c", s, tag) if tag else text.insert("end-1c", s)
    text.insert("end-1c", "\n")
    text.see(tkinter.END)
    text.config(state=tkinter.DISABLED)

def console_overwrite(text, segments):
    text.config(state=tkinter.NORMAL)
    text.delete("end-1c linestart", "end-1c")
    for tag, s in segments:
        text.insert("end-1c", s, tag) if tag else text.insert("end-1c", s)
    text.see(tkinter.END)
    text.config(state=tkinter.DISABLED)

def console_finish(console):
    console['button'].config(text="Close", command=console['window'].destroy)
    console['text'].after(0, console_append, console['text'], [(None, '[Process done]')])

def download_gui(link, place, formattie, button, proc_holder):
    if formattie.curselection():
        formattie = [formattie.get(i) for i in formattie.curselection()][0]
    else:
        formattie = fileformats[0]

    url = link.get()
    output_dir = place.get()

    if button:
        button.config(text="Downloading... (see console)", state=tkinter.DISABLED)

    console = open_console_window(proc_holder)

    def worker():
        try:
            safe_download(url, formattie, output_dir, ytdlplocate, proc_holder, console)
        finally:
            if button:
                button.after(0, lambda: button.config(text="Download", state=tkinter.NORMAL))
            console['window'].after(0, console_finish, console)

    threading.Thread(target=worker, daemon=True).start()

def interrupt_gui(proc_holder, console):
    proc = proc_holder.get('process')
    if proc is None or proc.poll() is not None:
        console['text'].after(0, console_append, console['text'], [(None, '[No active download to interrupt]')])
        return

    proc_holder['interrupted'] = True
    try:
        if os.name == 'nt':
            subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)], creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            os.killpg(proc.pid, signal.SIGINT)
        console['text'].after(0, console_append, console['text'], [(None, '[Interrupt sent]')])
    except Exception as e:
        console['text'].after(0, console_append, console['text'], [(None, f'[Could not interrupt: {e}]')])

def download(url, fmt, output_dir, yt_dlp_exe, proc_holder, console):
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

    creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    popen_kwargs = {'stdout': subprocess.PIPE, 'stderr': subprocess.STDOUT, 'bufsize': 0, 'creationflags': creationflags}
    if os.name != 'nt':
        popen_kwargs = {'stdout': subprocess.PIPE, 'stderr': subprocess.STDOUT, 'bufsize': 0, 'start_new_session': True}
    proc = subprocess.Popen(args, **popen_kwargs)
    proc_holder['process'] = proc

    reader = io.TextIOWrapper(proc.stdout, encoding='utf-8', errors='replace', newline='')
    segments = []
    buf = ''
    fg = None
    bold = False

    def flush_buf():
        nonlocal buf
        if buf:
            segments.append((ansi_tag(fg, bold), buf))
            buf = ''

    try:
        while True:
            ch = reader.read(1)
            if ch == '':
                break
            if ch == '\x1b':
                nxt = reader.read(1)
                if nxt != '[':
                    continue
                params = ''
                terminator = ''
                while True:
                    c2 = reader.read(1)
                    if c2 == '':
                        break
                    if c2.isalpha() or c2 in '@~':
                        terminator = c2
                        break
                    params += c2
                if terminator == 'm':
                    flush_buf()
                    fg, bold = sgr_apply(params, fg, bold)
                continue
            if ch == '\r':
                flush_buf()
                if segments:
                    console['text'].after(0, console_overwrite, console['text'], segments)
                segments = []
            elif ch == '\n':
                flush_buf()
                console['text'].after(0, console_append, console['text'], segments)
                segments = []
            else:
                buf += ch
        flush_buf()
        if segments:
            console['text'].after(0, console_append, console['text'], segments)
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


def safe_download(url, fmt, output_dir, yt_dlp_exe, proc_holder, console):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    before = set(os.listdir(output_dir))
    proc_holder['interrupted'] = False
    try:
        result = download(url, fmt, output_dir, yt_dlp_exe, proc_holder, console)
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


    urlframe = tkinter.Frame()

    urlframe.grid_columnconfigure(1, weight=1)
    urlframe.grid_columnconfigure(2, weight=0)

    tkinter.Label(urlframe, text="URL").grid(column=1, columnspan=2, row=0, sticky="WE")

    urlthing = tkinter.Entry(urlframe)
    urlthing.grid(column=1, row=1, sticky="WE")

    clearurl = tkinter.Button(urlframe, text="Clear", width=5, command=lambda:urlthing.delete(0, tkinter.END))
    clearurl.grid(column=2, row=1, sticky="WE")

    urlframe.pack(fill=tkinter.X)


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

    tkinter.ttk.Separator().pack(fill=tkinter.X)

    if os.path.exists(configs):
        def opc(*args):
            con = open_console_window(configholder, True)
            with open(configs) as c:
                con['text'].insert(tkinter.END, c.read())
            def sav(wr, *args):
                if con['button'].cget('text') == "Save":
                    with open(configs, 'w') as co:
                        co.write(wr)
                    con['button'].config(text='Close')
                else:
                    con['window'].destroy()
            con['button'].config(command=lambda:sav(con['text'].get("1.0","end-1c")))
            con['text'].edit_modified(False)
            def coc(event):
                if con['text'].edit_modified():
                    con['button'].config(text='Save')
            con['text'].bind("<<Modified>>", coc)
            
        configholder = {'process': None, 'interrupted': False}
        openconfig = tkinter.Button(text="Open config file", command=opc)
        openconfig.pack(fill=tkinter.X)

    tkinter.ttk.Separator().pack(fill=tkinter.X)

    downl = tkinter.Button(text="Download", font=(("Arial", 15, "bold")))
    downl.config(command=lambda:download_gui(urlthing, outputthing, formatthing, downl, proc_holder))
    downl.pack(expand=True, fill=tkinter.X)

    root.focus_force()
    urlthing.focus_set()
    
    root.mainloop()




if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        tkinter.messagebox.showerror("Error", str(e))
