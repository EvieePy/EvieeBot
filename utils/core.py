import discord
from discord.ext import commands
from discord.backoff import ExponentialBackoff
from discord.gateway import DiscordWebSocket, ResumeWebSocket

import aiohttp
import asyncio
import concurrent.futures
import configparser
import datetime
import inspect
import sys
import traceback
import websockets

from cryptography.fernet import Fernet
import utils


__all__ = ('config', 'Bot', 'evieeloads')

config = configparser.ConfigParser()
config.read('../config.ini')


class Bot(commands.Bot):

    def __init__(self, *args, **kwargs):

        # Async Init
        self.pool = None
        self.session = None

        # Caches
        self.cache_prefix = utils.LFUCache(limit=1000)

        # Message Encryption
        self.fernet = Fernet(config.get('ENCRYPTION', 'token').encode())

        self._reconnecting = asyncio.Event()
        super().__init__(*args, **kwargs)

    def is_reconnecting(self):
        """Return the bots reconnection state."""
        return self._reconnecting.is_set()

    async def _connect(self):
        coro = DiscordWebSocket.from_client(self, shard_id=self.shard_id)
        self.ws = await asyncio.wait_for(coro, timeout=180.0, loop=self.loop)

        self._reconnecting.clear()  # We are connected at this point.

        while True:
            try:
                await self.ws.poll_event()
            except ResumeWebSocket as e:
                coro = DiscordWebSocket.from_client(self,
                                                    shard_id=self.shard_id,
                                                    session=self.ws.session_id,
                                                    sequence=self.ws.sequence,
                                                    resume=True)
                self.ws = await asyncio.wait_for(coro, timeout=180.0, loop=self.loop)

    async def connect(self, *, reconnect=True):
        """Override connect and add a reconnecting state."""
        backoff = ExponentialBackoff()

        while not self.is_closed():
            try:
                await self._connect()
            except (OSError,
                    discord.HTTPException,
                    discord.GatewayNotFound,
                    discord.ConnectionClosed,
                    aiohttp.ClientError,
                    asyncio.TimeoutError,
                    websockets.InvalidHandshake,
                    websockets.WebSocketProtocolError) as e:

                if not reconnect:
                    await self.close()
                    if isinstance(e, discord.ConnectionClosed) and e.code == 1000:
                        # clean close, don't re-raise this
                        return
                    raise

                if self.is_closed():
                    return

                if isinstance(e, discord.ConnectionClosed):
                    if e.code != 1000:
                        await self.close()
                        raise

                retry = backoff.delay()
                self._reconnecting.set()
                await asyncio.sleep(retry, loop=self.loop)


async def run_in_executor(func, executor: concurrent.futures.Executor = None, loop=None, *args):
    if not loop:
        loop = asyncio.get_event_loop()

    if not executor:
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=20)

    future = executor.submit(func, *args)
    future = asyncio.wrap_future(future)

    result = await asyncio.wait_for(future, timeout=None, loop=loop)
    return result


def evieeloads(func):
    """Decorator which allows timing and handling of startup methods."""
    async def wrapper(*args, **kwargs):
        started = datetime.datetime.utcnow()

        try:
            if inspect.iscoroutinefunction(func):
                await func(*args, **kwargs)
            else:
                func(*args, **kwargs)
        except Exception:
            print(f'\n\n[CRITICAL] | Startup failure in call to function <{func.__name__}>\n', file=sys.stderr)
            traceback.print_exc()

            # Allow eviee to call shutdown
            raise utils.StartupFailure

        ended = datetime.datetime.utcnow()
        return print(f'{func.__name__}: {ended - started}')
    return wrapper

