import discord

import asyncio
import audioop
import json
import math
import subprocess
import youtube_dl
from functools import partial

import eaudio
import utils


def get_duration(url):
    try:
        cmd = f'ffprobe -v error -show_format -of json {url}'
        process = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = process.communicate()
        data = json.loads(output)
        match = data['format']['duration']
        process.kill()
    except Exception:
        # Fucking annoying
        return 0

    return math.ceil(float(match))


ytdlopts = {
    'format': 'bestaudio/best',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'  # ipv6 addresses cause issues sometimes
}

ffmpegopts = {
    'before_options': '-nostdin',
    'options': '-vn'
}


class YTDLSource(discord.PCMVolumeTransformer):

    def __init__(self, source, *, data, requester, filename):
        super().__init__(source)
        self.requester = requester
        self.filename = filename
        self.data = data

        self.volume = data.get('volume', 0.5)
        self.frames = 0
        self.url = data.get('url')
        self.duration = data.get('duration')
        self.thumb = data.get('thumbnail')
        self.channel = data.get('channel')
        self._original = data.get('_original', None)
        self.title = data.get('title')
        self.web_url = data.get('webpage_url')
        self.id = data.get('id')

        # YTDL info dicts (data) have other useful information you might want
        # https://github.com/rg3/youtube-dl/blob/master/README.md

    def __getitem__(self, item: str):
        """Allows us to access attributes similar to a dict.

        This is only useful when you are NOT downloading.
        """
        return self.__getattribute__(item)

    def read(self, volume=None):
        self.frames += 1
        return audioop.mul(super().read(), 2, volume or self.volume)

    @property
    def length(self):
        return self.duration

    @property
    def progress(self):
        return math.floor(self.frames/50)

    @property
    def remaining(self):
        return self.length - self.progress

    @classmethod
    async def create_source(cls, ctx, search: str, *, loop, volume, download=True):
        loop = loop or asyncio.get_event_loop()

        ytdlopts['outtmpl'] = f'downloads/{ctx.guild.id}/%(extractor)s-%(id)s-%(title)s.%(ext)s'
        ytdl = youtube_dl.YoutubeDL(ytdlopts)

        to_run = partial(ytdl.extract_info, url=search, download=download)
        data = await utils.evieecutor(func=to_run, executor=None, loop=loop)

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        data['duration'] = data.get('duration', get_duration(data['url']))
        data['channel'] = ctx.channel
        data['volume'] = volume

        if download:
            source = ytdl.prepare_filename(data)
        else:
            source = data['url']

        return cls(discord.FFmpegPCMAudio(source), data=data, requester=ctx.author, filename=source)

    @classmethod
    async def copy_source(cls, controller, source):
        opts = {'before_options': '-nostdin',
                'options': f'{controller.eq["filter"]}"'}

        source.data['volume'] = controller.volume

        return cls(discord.FFmpegPCMAudio(source.filename, **opts), data=source.data, requester=source.requester,
                   filename=source.filename)

    @classmethod
    async def edit_source(cls, controller, source, _filter, skip=False):
        opts = {'before_options': f'-ss {source.progress} -nostdin',
                'options': f'{_filter["filter"]}"'}

        source.data['volume'] = controller.volume

        return cls(discord.FFmpegPCMAudio(source.filename, **opts), data=source.data, requester=source.requester,
                   filename=source.filename)
    """
    @classmethod
    async def regather_stream(cls, data, *, loop):
        loop = loop or asyncio.get_event_loop()
        requester = data['requester']

        to_run = partial(ytdl.extract_info, url=data['webpage_url'], download=False)
        data = await utils.evieecutor(func=to_run, executor=None, loop=loop)

        return cls(discord.FFmpegPCMAudio(data['url']), data=data, requester=requester, filename=None)
    """