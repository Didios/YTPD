import os
from tkinter import Tk, Entry, Button, StringVar, Label, Frame, IntVar, BooleanVar, Checkbutton, Canvas
from tkinter.ttk import Combobox, Progressbar
from tkinter.filedialog import askdirectory
from tkinter.messagebox import showerror, showinfo, askyesno

from threading import Thread
from os import path, rename

import pytube.exceptions
import validators

import re
from pytube import Playlist, YouTube
import pytube.extract

import urllib.request
import io
from PIL import ImageTk, Image

import sys
def resource_path(relative):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = path.abspath(".")

    return path.join(base_path, relative)


class YTPD:
    THUMBNAIL_SIZE = (640, 360)

    def __init__(self):
        self.root = Tk()
        self.root.title('Youtube Downloader')
        self.root.iconbitmap(resource_path('assets/icon.ico'))

        self.main_frame = Frame(self.root)
        self.download_frame = Frame(self.root)

        self.url = StringVar()
        self.output = StringVar()
        self.extension = StringVar()
        self.crush = BooleanVar()

        self.progress_value = IntVar()
        self.progress_text = StringVar()
        self.thumbnail_canvas = None
        self.thumbnail_data = None
        self.thumbnail_image = None
        self.title = StringVar()

        self.__set_main_frame()
        self.__set_download_frame()
        self.__set_rescale()

    def launch(self):
        self.extension.set('mp3')
        self.set_progress(0, 0)
        self.crush.set(False)
        self.title.set("")

        self._to_main_frame()
        self.root.mainloop()

# region configurations

    def __set_main_frame(self):
        Label(self.main_frame, text='url:').grid(row=0, column=0, sticky='nsew')
        Entry(self.main_frame, textvariable=self.url).grid(row=0, column=1, columnspan=2, sticky='nsew')

        Label(self.main_frame, text='Output folder:').grid(row=1, column=0, sticky='nsew')
        Entry(self.main_frame, textvariable=self.output).grid(row=1, column=1, sticky='nsew')
        Button(self.main_frame, text='Browse', width=10, command=self.get_output).grid(row=1, column=2, sticky='nsew')

        extensions = ('mp3', 'webm', 'mp4')
        Label(self.main_frame, text='Extension').grid(row=2, column=0, sticky='nsew')
        Combobox(self.main_frame, textvariable=self.extension,
                 values=extensions, state='readonly').grid(row=2, column=1, columnspan=2, sticky='nsew')

        Label(self.main_frame, text='Crush existing files').grid(row=3, column=0, sticky='nsew')
        Checkbutton(self.main_frame, anchor='center', variable=self.crush,
                    onvalue=True, offvalue=False).grid(row=3, column=1, columnspan=2, sticky='nsew')

        Button(self.main_frame, text='Download', command=self.download).grid(row=4, column=0, columnspan=3, sticky='nsew')

    def __set_download_frame(self):
        self.thumbnail_canvas = Canvas(self.download_frame,
                                       width=self.THUMBNAIL_SIZE[0], height=self.THUMBNAIL_SIZE[1], background='black')
        self.thumbnail_canvas.grid(row=0, column=0, sticky='nsew')
        self.thumbnail_canvas.bind('<Configure>', self.resize_thumbnail)

        Label(self.download_frame, textvariable=self.title).grid(row=1, column=0, sticky='nsew')

        Progressbar(self.download_frame, orient='horizontal', mode='determinate',
                    variable=self.progress_value).grid(row=2, column=0, sticky='nsew')

        Label(self.download_frame, textvariable=self.progress_text).grid(row=3, column=0, sticky='nsew')

    def __set_rescale(self):
        self.main_frame.rowconfigure(0, weight=2)
        self.main_frame.rowconfigure(1, weight=2)
        self.main_frame.rowconfigure(2, weight=2)
        self.main_frame.rowconfigure(3, weight=0)
        self.main_frame.rowconfigure(4, weight=1)

        self.main_frame.columnconfigure(0, weight=0)
        self.main_frame.columnconfigure(1, weight=1)
        self.main_frame.columnconfigure(2, weight=0)

        self.download_frame.rowconfigure(0, weight=1)
        self.download_frame.rowconfigure(1, weight=1)
        self.download_frame.rowconfigure(2, weight=1)
        self.download_frame.rowconfigure(3, weight=1)

        self.download_frame.columnconfigure(0, weight=1)

        self.root.minsize(450, 150)
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)

# endregion configurations

# region frame management

    def _to_main_frame(self):
        self.download_frame.grid_forget()
        self.main_frame.grid(row=0, column=0, sticky='nsew')

    def _to_download_frame(self):
        self.main_frame.grid_forget()
        self.download_frame.grid(row=0, column=0, sticky='nsew')

# endregion frame management

    def get_output(self):
        new_output = askdirectory(title='Choose Output Folder')

        if new_output and new_output != '':
            self.output.set(new_output)

    def set_progress(self, current_value, max_value):
        if max_value == 0:
            self.progress_value.set(0)
        else:
            self.progress_value.set(current_value / max_value * 100)

        self.progress_text.set(f'{current_value} / {max_value}')

    def show_thumbnail(self, video):
        raw_data = urllib.request.urlopen(video.thumbnail_url).read()

        self.thumbnail_data = Image.open(io.BytesIO(raw_data)).resize(self.THUMBNAIL_SIZE)
        self.thumbnail_image = ImageTk.PhotoImage(self.thumbnail_data)

        self.thumbnail_canvas.delete('all')
        self.thumbnail_canvas.create_image(0, 0, anchor='nw', image=self.thumbnail_image)

    def resize_thumbnail(self, event):
        self.THUMBNAIL_SIZE = (event.width, event.height)

        if self.thumbnail_data is not None:
            # resize thumbnail
            self.thumbnail_data = self.thumbnail_data.resize(self.THUMBNAIL_SIZE)
            self.thumbnail_image = ImageTk.PhotoImage(self.thumbnail_data)

            # recreate thumbnail
            self.thumbnail_canvas.delete('all')
            self.thumbnail_canvas.create_image(0, 0, anchor='nw', image=self.thumbnail_image)

    def __set_video_info(self, video):
        self.show_thumbnail(video)
        self.title.set(video.title)

# region download

    def __download_playlist(self):
        playlist = Playlist(self.url.get())
        playlist._video_regex = re.compile(r"\"url\":\"(/watch\?v=[\w-]*)")

        playlist_len = len(playlist.video_urls)

        output = self.output.get()
        extension = self.extension.get()

        for i, url in enumerate(playlist.video_urls):
            self.set_progress(i, playlist_len)

            self.__download_content(url, output, extension)

        self.set_progress(playlist_len, playlist_len)
        showinfo('Success', f'Playlist have been successfully downloaded in:\n{output}')
        self._to_main_frame()

    def __download_video(self):
        self.set_progress(0, 1)

        url = self.url.get()
        output = self.output.get()
        extension = self.extension.get()

        self.__download_content(url, output, extension)

        self.set_progress(1, 1)
        showinfo('Success', f'Video has been successfully downloaded in:\n{output}')
        self._to_main_frame()

    def __download_content(self, url, output, extension):
        video = YouTube(url)
        filename = re.sub(r'[^\w\-_\. ]', '_', f'{video.title}.{extension}')
        filepath = path.join(output, filename)

        create = True
        if path.exists(filepath):
            if not self.crush.get():
                create = False

        self.__set_video_info(video)

        if create:
            if extension == 'mp3':
                videofile = video.streams.filter(only_audio=True).first()
            else:
                videofile = video.streams.filter(file_extension=extension).first()

            videofile.download(output_path=output, filename=filename)


    def download(self):
        # check folder
        folder = self.output.get()
        if not path.exists(folder):
            showerror('Folder error', f'The folder specified does not exist:\n{folder}')
            return

        # check url
        url = self.url.get()
        if not (validators.url(url) and 'youtube.com' in url):
            showerror('Url error', f'The provided url is not valid:\n{url}')
            return

        # check if playlist
        isPlaylist = False
        if '/playlist?list=' in url or ('/watch' in url and 'list=' in url):
            isPlaylist = True

        # setup and launch
        self.set_progress(0, 0)
        self._to_download_frame()
        if isPlaylist:
            t = Thread(target=self.__download_playlist)
            #self.__download_playlist()
        else:
            t = Thread(target=self.__download_video)
            #self.__download_video()
        t.start()

# endregion download


if __name__ == '__main__':
    app = YTPD()
    app.launch()

