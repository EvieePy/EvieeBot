"""
The MIT License (MIT)

Copyright (c) 2015-2018 Rapptz
Copyright (c) 2018 EvieePy


Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""
import discord
from discord.ext import commands
from discord.backoff import ExponentialBackoff
from discord.gateway import DiscordWebSocket, ResumeWebSocket

import aiohttp
import asyncio
import asyncpg
import configparser
import datetime
import importlib
import inspect
import itertools
import pathlib
import psutil
import os
import sys
import time
import traceback
import websockets
from collections import deque
from cryptography.fernet import Fernet

import utils

try:
    import uvloop
except ImportError:
    pass
except AttributeError:
    # For 3.7 testing...
    pass
else:
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
finally:
    loop = asyncio.get_event_loop()


config = configparser.ConfigParser()
config.read('config.ini')


async def get_prefix(bot_, msg):
    if not msg.guild:
        return bot_.defaults

    if bot_.lru_prefix.get(msg.guild.id):
        lru = sorted(bot_.lru_prefix[msg.guild.id], reverse=True)
        return commands.when_mentioned_or(*lru)(bot_, msg)

    async with bot_.pool.acquire() as conn:
        async with conn.transaction():
            ret = await conn.fetchval("""SELECT prefixes FROM guilds WHERE id IN ($1)""", msg.guild.id)
            if not ret:
                query = """INSERT INTO guilds(id, prefixes) VALUES($1, $2) ON CONFLICT (id)
                           DO UPDATE SET prefixes = $2 WHERE guilds.id IN ($1)"""
                await conn.execute(query, msg.guild.id, bot_.defaults)
                ret = bot_.defaults

    ret = sorted(ret, reverse=True)
    bot_.lru_prefix[msg.guild.id] = [*ret]
    return commands.when_mentioned_or(*ret)(bot_, msg)


class Botto(commands.Bot):
    """The main bot class."""

    def __init__(self):
        self.loop = loop
        self.initialised = False
        self.pool = None  # Async init
        self.session = None  # Async init
        self.proc = psutil.Process()
        self.owners = (402159684724719617, 214925855359631360)
        self.starttime = datetime.datetime.utcnow()

        self.defaults = {'eviee ', 'eviee pls '}  # Prefix Defaults
        self.lru_prefix = utils.EvieeLRU(name='Prefix LRU', limit=120)
        self.lru_blocks = utils.EvieeLRU(name='Blocks LRU', limit=500)
        self._wspings = deque(maxlen=60)
        self._rtts = deque(maxlen=60)

        self._config = config
        self._abstract_commands = None
        self._reconnecting = asyncio.Event()
        self._last_result = None
        self.categories = {}
        self.extensions_other = {}

        self.fkey = Fernet(config.get('ENCRYPTION', '_token').encode())

        super().__init__(command_prefix=get_prefix)

    def is_reconnecting(self):
        """Return the bots reconnection state."""
        return self._reconnecting.is_set()

    @utils.evieeloads
    async def async_init(self):
        """Async Initializer."""
        self.remove_command('help')
        self.pool = await asyncpg.create_pool(f'postgres://postgres:{config.get("DB", "_pass")}@localhost:5432/eviee')
        self.session = aiohttp.ClientSession(loop=self.loop)

        await self.load_cache()
        await self.load_modules()
        await self.load_abstractors()

        self.loop.create_task(self.wspings())
        self.loop.create_task(self.rttpings())

    @utils.backoff_loop()
    async def wspings(self):
        await asyncio.sleep(60)
        self._wspings.append(self.latency * 1000)

    @utils.backoff_loop()
    async def rttpings(self):
        chan = self.get_channel(434972274467274762)

        ts = time.time()
        msg = await chan.send('Ping!')
        rtt = (time.time() - ts) * 1000

        self._rtts.append(rtt)
        await msg.delete()

        await asyncio.sleep(60)

    @utils.evieeloads
    async def load_cache(self):
        pass

    def load_extension(self, name):
        """Default lib load_extension with a custom exception for better handling."""
        if name in self.extensions:
            return

        lib = importlib.import_module(name)
        if hasattr(lib, 'setup'):
            lib.setup(self)
            self.extensions[name] = lib
        else:
            for n, m in inspect.getmembers(lib):
                if inspect.isclass(m) and type(m) == utils.MetaCog:
                    try:
                        m(self)
                    except Exception as e:
                        print(e)

                    if name not in self.extensions:
                        self.extensions[name] = lib
                else:
                    self.extensions_other[name] = lib
                    continue

        if name not in self.extensions:
            del lib
            del sys.modules[name]
            # This way we can explicitly catch cogs without setup functions
            raise utils.ImportFailure(f'The extension {name} does not have a setup function.')

    @utils.evieeloads
    async def load_modules(self):
        """Load our cogs.

        This coroutine handles recursive directory checking for cogs and ignores everything else.
        """

        # A bit messy(but hey it works)
        modules = [f'{p.parent}.{p.stem}' for p in pathlib.Path('.').rglob('*.py')
                   if not str(p.parent).startswith('venv') and not p.stem.startswith(('main', '__'))]
        failed = []

        for extension in modules:
            try:
                self.load_extension(extension)
            except utils.ImportFailure:
                pass
            except Exception as e:
                failed.append(f'{extension}: {e}')
                print(f'Failed to load extension <{extension}>.', file=sys.stderr)
                traceback.print_exception(etype=type(e), tb=e.__traceback__, value=e)

        if failed:
            print('\n\nThe following extensions failed to load:\n{}\n'.format('\n'.join(f for f in failed)))

    @utils.evieeloads
    async def load_abstractors(self):
        """Abstractor command loader.

        Without this coroutine the bot will essentially break.
        Read /utils/core for more info."""
        self._abstract_commands = {c.name: [] for c in self.commands if isinstance(c, utils.AbstractorCommand)}

        for command in self.commands:
            if not isinstance(command, utils.AbstractorGroup):
                continue

            for abstractor in command.abstractors:
                if abstractor in self._abstract_commands:
                    self._abstract_commands[abstractor].extend([command.name, *command.aliases])
                else:
                    raise utils.AbstractorException(f'Failed to add abstractor to group <{command.name}>.'
                                                    f' No abstractor named "{abstractor}" exists.')

    async def process_commands(self, ctx):
        """Override process commands.

        This allows us to support AbstractorCommands."""
        if not ctx.command:
            raise commands.CommandNotFound('Command "{}" is not found'.format(ctx.invoked_with))

        if ctx.command.name in self._abstract_commands:
            view = ctx.view
            view.skip_ws()

            # The command group name...
            trigger = view.get_word()

            if not trigger:
                raise utils.MissingCommand(f'Missing command for abstractor "{ctx.command.name}".')

            abstractors = self._abstract_commands[ctx.command.name]

            if trigger in abstractors:
                command = self.get_command(f'{trigger} {ctx.command.name}')
            else:
                raise utils.InvalidCommand(f'Command "{trigger}" is invalid for abstractor "{ctx.command.name}".')

            if not command:
                raise commands.CommandNotFound(f'Command "{trigger} {ctx.command.name}" was not found while trying '
                                               f'to invoke abstractor "{ctx.command.name} {trigger}".')

            return command
        return

    async def on_message(self, message):
        """Override on message.

        Here we create a custom Context and ignore all CommandNotFound errors by default."""
        if message.author.bot:
            return

        ctx = await self.get_context(message, cls=utils.EvieeContext)

        if not ctx.prefix:
            return

        try:
            command = await self.process_commands(ctx)
        except Exception as e:
            if isinstance(e, commands.CommandNotFound):
                return
            return self.dispatch('command_error', ctx, e)

        if command:
            try:
                await command.invoke(ctx)
            except Exception as e:
                await command.dispatch_error(ctx, e)
        else:
            await self.invoke(ctx)

    async def on_ready(self):
        if config.get('RESTART', 'mid') != '0':
            chan = self.get_channel(int(config.get('RESTART', 'cid')))
            msg = await chan.get_message(int(config.get('RESTART', 'mid')))

            config.set('RESTART', 'cid', '0')
            config.set('RESTART', 'mid', '0')

            with open('config.ini', 'w') as configfile:
                config.write(configfile)

            await msg.edit(embed=discord.Embed(description='<:reset_on:449475278037712906> **`- Back Online...`**',
                                               colour=0x8abe00))

        if not self.initialised:
            self.initialised = True
            print(f'Total Startup: {datetime.datetime.utcnow() - self.starttime}')
            await self.change_presence(activity=
                                       discord.Activity(name='the world go by...',
                                                        type=discord.ActivityType.watching,
                                                        state='In Hell',
                                                        details="All alone she was living..."))

        print(f'\n{"~"*20}\n\nLogged in as: {str(self.user)} ID(: {self.user.id})\n\n{"~"*20}\n\n')

    async def aio(self, method, url, return_attr: str=None, **kwargs):
        async with self.session.request(method, url, **kwargs) as resp:
            if not return_attr:
                return resp
            cont = getattr(resp, return_attr)
            return resp, await cont()

    async def create_bin(self, data):
        try:
            resp, respj = await self.aio('post', url='http://mystb.in/documents', return_attr='json', data=data)
        except Exception as e:
            return

        return f'http://mystb.in/{respj["key"]}'

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

    def get_category(self, name: str):
        return self.categories.get(name, None)

    def get_category_commands(self, name: str):
        category = self.get_category(name)

        if not category:
            return None

        return set(itertools.chain.from_iterable([c.commands for c in category]))

    def get_category_events(self, name: str):
        category = self.get_category(name)

        if not category:
            return None

        return {k: v for (k, v) in [(type(n).__name__, n.events) for n in category]}

    def get_ext(self, name: str):
        ext = self.extensions.get(name, None)
        if not ext:
            ext = self.extensions_other.get(name, None)

        return ext


bot = Botto()


async def shutdown(*, reason=None):
    """Somewhat clean shutdown with basic debug info."""
    await bot.logout()

    print(f'\n\nShutting down due to {type(reason).__name__}...\n{"="*30}\n')
    print(f'{datetime.datetime.utcnow()} || UTC\n\nPython: {sys.version}\nPlatform: {sys.platform}/{os.name}\n'
          f'Discord: {discord.__version__}\n\n{"="*30}\n')

    await asyncio.sleep(1)

    if isinstance(reason, KeyboardInterrupt):
        sys.exit(1)  # Systemd will think it failed and restart our service cleanly.
    sys.exit(0)


@bot.command(name='restart', cls=utils.EvieeCommand)
@commands.is_owner()
async def do_restart(ctx):
    embed = discord.Embed(description='<:reset_init:449475270144163840> **`- Initialising...`**', colour=0xab00c5)
    msg = await ctx.send(embed=embed)

    config.set('RESTART', 'cid', str(ctx.channel.id))
    config.set('RESTART', 'mid', str(msg.id))

    with open('config.ini', 'w') as configfile:
        config.write(configfile)

    await asyncio.sleep(2)
    cog = bot.get_cog('Music')

    if cog.controllers:
        embed.description = '<:reset_init:449475270144163840> **`- Waiting for Music Controllers to die...`**'
        await msg.edit(embed=embed)

    while cog.controllers:
        await asyncio.sleep(10)

    embed.description = '<:reset_off:449475278079524864> **`- Offline...`**'
    embed._colour = discord.Colour(0xc12400)
    await msg.edit(embed=embed)

    raise KeyboardInterrupt


def start():
    """Start and run the but, calling shutdown on exit."""
    print('\n\nStarting Eviee...\n')
    try:
        loop.run_until_complete(bot.async_init())
    except utils.StartupFailure as e:
        return loop.run_until_complete(shutdown(reason=e))

    try:
        loop.run_until_complete(bot.start(config.get('TOKEN', '_tokent')))
    except KeyboardInterrupt as e:
        return loop.run_until_complete(shutdown(reason=e))


start()

