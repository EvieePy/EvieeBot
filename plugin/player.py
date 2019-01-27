import asyncio
import datetime
import discord
import itertools
import math
import wavelink
from discord.ext import commands
from typing import Union

from .queue import Queue
import utils


class Track(wavelink.Track):
    __slots__ = ('requester', 'channel', 'message', 'ctx')

    def __init__(self, id_, info, *, query=None, ctx=None):
        super(Track, self).__init__(id_, info)
        self.ctx = ctx
        self.query = query

        self.requester = ctx.author
        self.channel = ctx.channel
        self.message = ctx.message

    def __str__(self):
        return self.title

    @property
    def is_dead(self):
        return self.dead


class Player(wavelink.Player):

    __slots__ = ('next_event', 'queue', 'volume', 'dj', 'is_playing', 'update', 'updating', 'controller_message',
                 'reaction_task', 'controls', 'inactive', 'pauses', 'resumes', 'stops', 'skips',
                 'shuffles', 'repeats', 'last_seen', 'backs', 'was_back')

    def __init__(self, bot: Union[commands.Bot, commands.AutoShardedBot], guild_id: int, node: wavelink.Node):
        super(Player, self).__init__(bot, guild_id, node)

        self.next_event = asyncio.Event()
        self.queue = Queue()

        self.volume = 40
        self.dj = None
        self.controller_message = None
        self.reaction_task = None

        self.update = False
        self.updating = False
        self.inactive = False
        self.is_playing = False
        self.last_seen = None
        self.was_back = False

        self._player_loop = bot.loop.create_task(self.player_loop())
        self._manual_updater = bot.loop.create_task(self.manual_updater())

        self._tasks = [self._player_loop, self._manual_updater]

        self.controls = {'⏯': 'rp',
                         '⏮': 'back',
                         '⏹': 'stop',
                         '⏭': 'skip',
                         '\U0001F500': 'shuffle',
                         '\U0001F502': 'repeat',
                         '➕': 'vol_up',
                         '➖': 'vol_down',
                         '\U0001F1F6': 'queue'}

        self.pauses = set()
        self.resumes = set()
        self.stops = set()
        self.shuffles = set()
        self.skips = set()
        self.repeats = set()
        self.backs = set()

    async def manual_updater(self):
        while not self.bot.is_closed():
            if self.update and not self.updating:
                self.update = False
                await self.invoke_controller()

            await asyncio.sleep(10)

    async def player_loop(self):
        await self.bot.wait_until_ready()
        await self.set_volume(40)

        while True:
            self.next_event.clear()
            self.inactive = False

            song = await self.queue.find_next()

            if not song.id:
                songs = await self.bot.wavelink.get_tracks(f'ytsearch:{song.query}')

                if not songs:
                    continue

                try:
                    song_ = songs[0]
                    song = Track(id_=song_.id, info=song_.info, ctx=song.ctx)
                except Exception as e:
                    print(e)
                    continue

            self.is_playing = True

            await self.play(song)
            self.queue.backwards.appendleft(song)

            if not self.update:
                await self.invoke_controller()

            await self.next_event.wait()
            self.is_playing = False

            self.pauses.clear()
            self.resumes.clear()
            self.stops.clear()
            self.shuffles.clear()
            self.skips.clear()
            self.repeats.clear()
            self.backs.clear()

    async def invoke_controller(self, track: Track = None):
        if not track:
            track = self.current

        self.updating = True

        embed = discord.Embed(title='Music Controller', description=f'Now Playing:```\n{track.title}\n```',
                              colour=0xffb347)
        # embed.set_thumbnail(url='https://i.imgur.com/9JajaIq.png')
        embed.set_thumbnail(url=track.thumb)

        if track.is_stream:
            embed.add_field(name='Duration', value='🔴`Streaming`')
        else:
            completed = str(datetime.timedelta(milliseconds=int(self.position))).split('.')[0]
            duration = str(datetime.timedelta(milliseconds=int(track.duration))).split('.')[0]

            embed.add_field(name='Completed/Duration',
                            value=f'{completed if completed != duration else "0:00:00"}/{duration}')
        embed.add_field(name='Video URL', value=f'[Click Here!]({track.uri})')
        embed.add_field(name='Requested By', value=track.requester.mention)
        embed.add_field(name='Current DJ', value=self.dj.mention)
        embed.add_field(name='Queue Length', value=str(len([_ for _ in self.queue.entries if not _.is_dead])))
        # embed.add_field(name='Player Restrictions', value=f'`None`')
        embed.add_field(name='Volume', value=f'**`{self.volume}%`**')
        embed.set_footer(text='Made with love using WaveLink')

        if len(self.queue.entries) > 0:
            data = '\n'.join(f'**-** `{t.title[0:45]}{"..." if len(t.title) > 45 else ""}`\n{"-"*10}'
                             for t in itertools.islice([e for e in self.queue.entries if not e.is_dead], 0, 3, None))
            embed.add_field(name='Coming Up:', value=data or 'None', inline=False)

        if not await self.is_current_fresh(track.channel) and self.controller_message:
            try:
                await self.controller_message.delete()
            except discord.HTTPException:
                pass

            self.controller_message = await track.channel.send(embed=embed)
        elif not self.controller_message:
            self.controller_message = await track.channel.send(embed=embed)
        else:
            self.updating = False
            return await self.controller_message.edit(embed=embed, content=None)

        try:
            self.reaction_task.cancel()
        except Exception:
            pass

        self.reaction_task = self.bot.loop.create_task(self.reaction_controller())
        self.updating = False

    async def add_reactions(self):
        for reaction in self.controls:
            try:
                await self.controller_message.add_reaction(str(reaction))
            except Exception:
                return

    async def reaction_controller(self):
        self.bot.loop.create_task(self.add_reactions())

        def check(r, u):
            if not self.controller_message:
                return False
            elif str(r) not in self.controls.keys():
                return False
            elif u.id == self.bot.user.id or r.message.id != self.controller_message.id:
                return False
            elif u not in self.bot.get_channel(int(self.channel_id)).members:
                return False
            return True

        while self.controller_message:
            if self.channel_id is None:
                return self.reaction_task.cancel()

            react, user = await self.bot.wait_for('reaction_add', check=check)
            control = self.controls.get(str(react))

            if control == 'rp':
                if self.paused:
                    control = 'resume'
                else:
                    control = 'pause'

            if control == 'pageup':
                continue

            try:
                await self.controller_message.remove_reaction(react, user)
            except discord.HTTPException:
                pass
            cmd = self.bot.get_command(control)

            ctx = await self.bot.get_context(react.message, cls=utils.EvieeContext)
            ctx.author = user

            try:
                if cmd.is_on_cooldown(ctx):
                    pass
                if not await self.invoke_react(cmd, ctx):
                    pass
                else:
                    self.bot.loop.create_task(ctx.invoke(cmd))
            except Exception as e:
                ctx.command = self.bot.get_command('reactcontrol')
                await cmd.dispatch_error(ctx=ctx, error=e)

        await self.destroy_controller()

    async def destroy_controller(self):
        try:
            await self.controller_message.delete()
            self.controller_message = None
        except (AttributeError, discord.HTTPException):
            pass

        try:
            self.reaction_task.cancel()
        except Exception:
            pass

    async def invoke_react(self, cmd, ctx):
        if not cmd._buckets.valid:
            return True

        if not (await cmd.can_run(ctx)):
            return False

        bucket = cmd._buckets.get_bucket(ctx)
        retry_after = bucket.update_rate_limit()
        if retry_after:
            return False
        return True

    async def is_current_fresh(self, chan):
        try:
            async for m in chan.history(limit=8):
                if m.id == self.controller_message.id:
                    return True
        except (discord.HTTPException, AttributeError):
            return False
        return False
