"""
LICENSE:
Copyright (c) 2018 MysterialPy

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE."""
import discord
from discord.ext import commands

import asyncio
import datetime
import math
import random
import shutil
import time
from itertools import islice
from functools import partial

import eaudio
import utils


class PlayerController:

    __slots__ = ('bot', '__vc', 'PLAYER', 'skips', 'pauses', 'resumes', 'shuffles', 'volume', 'eq', 'active_loads',
                 'current_message', '_tasks', 'gid', 'last_seen', 'dj', 'reaction_task',
                 'restrictions', 'requested_loads', 'last_call', '_updates', 'state', 'repeats', 'after_state', 'me',
                 'restricted_plus', 'current_extras', 'extras_reaction_task', '__dc')

    IDLE = 0
    UPDATING = 1
    SHUFFLING = 2

    def __init__(self, bot, ctx):
        self.bot = bot
        self.gid = ctx.guild.id
        self.state = self.IDLE
        self.__dc = ctx.channel
        self.__vc = ctx.voice_client
        self.me = ctx.guild.me

        self.PLAYER = eaudio.AudioMixer(client=self.__vc,
                                        after=lambda e, o:
                                        bot.loop.call_soon_threadsafe(self.after_call, e, o),
                                        after_all=lambda e, t:
                                        bot.loop.call_soon_threadsafe(self.delegate_after_all, e, t),
                                        next_call=lambda n:
                                        bot.loop.call_soon_threadsafe(self.next_call, n))
        self.__vc._player = self.PLAYER

        self.skips = set()
        self.pauses = set()
        self.repeats = set()
        self.resumes = set()
        self.shuffles = set()

        self.dj = ctx.author
        self.volume = 0.4
        self.eq = eaudio.EQS.FLAT
        self.current_message = None
        self.current_extras = None

        self.restrictions = eaudio.RestrictionStatus.open
        self.restricted_plus = list(self.restricted).append('play')

        self.active_loads = 0
        self.requested_loads = 0
        self._tasks = {}
        self.reaction_task = None
        self.extras_reaction_task = None
        self.last_call = time.time()
        self.last_seen = None
        self.after_state = False
        self._updates = 0

        _starters = (self.updater_task, self.inactivity_check)

        for exc in _starters:
            task = bot.loop.create_task(exc())
            self._tasks[exc.__name__] = task

        self.PLAYER.do_start()

    @property
    def p1controls(self):
        return eaudio.PONE_CONTROLS

    @property
    def p2controls(self):
        return eaudio.PTWO_CONTROLS

    @property
    def restricted(self):
        return 'connect', 'resume', 'skip', 'stop', 'volume', 'vol_down', 'vol_up', 'eq'

    async def destroy_controller(self, task, message):
        try:
            await message.delete()
        except discord.HTTPException:
            pass

        try:
            task.cancel()
        except Exception:
            pass

    async def inactivity_check(self):
        while not self.bot.is_closed():
            await asyncio.sleep(30)

            if not self.last_seen:
                continue

            current = time.time()
            if current - self.last_seen >= 600:
                self.PLAYER.stop()

    async def updater_task(self):
        while not self.bot.is_closed():
            if not self.is_safe():
                pass
            elif self._updates > 0:
                self.bot.loop.create_task(self.message_controller())

            await asyncio.sleep(10)

    def is_safe(self):
        if self.active_loads > 0:
            return False

        if self.PLAYER.state >= 2:
            return False

        if self.after_state:
            return False

        return True

    def cleanup(self, old: tuple=None, *, gid):
        excs = []

        for source in old:
            try:
                source.cleanup()
            except Exception as e:
                excs.append(e)
                pass

        shutil.rmtree(f'./downloads/{gid}', ignore_errors=True)
        return excs

    def next_call(self, n):
        self.PLAYER.next = n

    def after_call(self, error, old):
        self.after_state = True
        try:
            old.cleanup()
        except Exception:
            pass

        self.skips.clear()
        self.pauses.clear()
        self.repeats.clear()
        self.resumes.clear()
        self.shuffles.clear()

        self.after_state = False

        if self.is_safe():
            self.bot.loop.create_task(self.message_controller())

    async def after_all_call(self, old):
        await self.__vc.disconnect(force=True)

        try:
            await self.current_message.delete()
            await self.current_extras.delete()
            # current_extras may not always exist, but it's likely current_message will
        except (AttributeError, discord.HTTPException):
            pass

        for task in self._tasks:
            try:
                task.cancel()
            except Exception:
                pass

        try:
            del self.bot.get_cog('Music').controllers[self.gid]
        except Exception:
            pass

        try:
            to_run = partial(self.cleanup, old, gid=self.gid)
            excs = await utils.evieecutor(func=to_run, executor=None, loop=self.bot.loop)
        except Exception as e:
            print(e)

    def delegate_after_all(self, error, o):
        self.bot.loop.create_task(self.after_all_call(o))

    async def extras_message_controller(self):
        if self.current_extras:
            return

        e = discord.Embed(title='Music Controller - Extra Controls',
                          description='**Press ℹ For information on Restriction Levels.**',
                          colour=self.eq['colour'])

        e.add_field(name='Equalizers', value='\U0001F1F7 = Rock\n'
                                             '\U0001F1F3 = Nightcore\n'
                                             '\U0001F1E7 = Boost\n')
        e.add_field(name='Restrictions', value='\u0030\u20E3 = Open\n'
                                               '\u0031\u20E3 = Semi Restricted\n'
                                               '\u0032\u20E3 = Semi Restricted+\n'
                                               '\u0033\u20E3 = Restricted\n'
                                               '\u0034\u20E3 = Restricted+\n')

        if self.PLAYER.current:
            channel = self.PLAYER.current.channel
        else:
            channel = self.__dc.send(embed=e)

        try:
            self.extras_reaction_task.cancel()
        except Exception:
            pass

        self.current_extras = await channel.send(embed=e)
        self.extras_reaction_task = self.bot.loop.create_task(self.extras_reaction_controller())

    async def extras_reaction_controller(self):
        vc = self.__vc

        for react in self.p2controls:
            await self.current_extras.add_reaction(str(react))

        def check(r, u):
            if not self.current_message:
                return False
            elif str(r) not in self.p2controls.keys():
                return False
            elif u.id == self.bot.user.id or r.message.id != self.current_extras.id:
                return False
            return True

        while self.current_extras:
            if vc is None:
                await self.destroy_controller(self.extras_reaction_task, self.current_extras)
                self.current_extras = None

            try:
                react, user = await self.bot.wait_for('reaction_add', check=check, timeout=90)
            except asyncio.TimeoutError:
                await self.destroy_controller(self.extras_reaction_task, self.current_extras)
                self.current_extras = None

            print(f'REACTION: {react}')
            pair = self.p2controls.get(str(react))
            control = pair[0]
            print(f'EXTRA CONTROL: {control}')

            try:
                await self.current_extras.remove_reaction(react, user)
            except discord.HTTPException:
                pass

            cmd = self.bot.get_command(control)
            value = pair[1]
            ctx = await self.bot.get_context(react.message, cls=utils.EvieeContext)
            ctx.author = user

            if control == 'eq':
                kwargs = {'equalizer': value}
            else:
                kwargs = {'level': value}

            try:
                if cmd.is_on_cooldown(ctx):
                    pass
                if not await self.invoke_react(cmd, ctx):
                    pass
                else:
                    self.bot.loop.create_task(ctx.invoke(cmd, **kwargs))
            except Exception as e:
                ctx.command = self.bot.get_command('reactcontrol')
                await cmd.dispatch_error(ctx=ctx, error=e)

        await self.destroy_controller(self.extras_reaction_task, self.current_extras)

    async def reaction_controller(self):
        vc = self.__vc

        for react in self.p1controls:
            await self.current_message.add_reaction(str(react))

        def check(r, u):
            if not self.current_message:
                return False
            elif str(r) not in self.p1controls.keys():
                return False
            elif u.id == self.bot.user.id or r.message.id != self.current_message.id:
                return False
            elif u not in vc.channel.members:
                return False
            return True

        while self.current_message:
            if vc is None:
                return self.reaction_task.cancel()

            react, user = await self.bot.wait_for('reaction_add', check=check)
            control = self.p1controls.get(str(react))

            if control == 'rp':
                if self.PLAYER.is_paused():
                    control = 'resume'
                else:
                    control = 'pause'

            print(f'CONTROL: {control}')

            try:
                await self.current_message.remove_reaction(react, user)
            except discord.HTTPException:
                pass

            cmd = self.bot.get_command(f'{"dj " if user.id == self.dj.id else ""}{control}')\
                or self.bot.get_command(control)

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

        await self.destroy_controller(self.reaction_task, self.current_message)

    async def message_controller(self, song=None):
        self._updates = 0

        if not song:
            if not self.PLAYER.current:
                return
            else:
                song = self.PLAYER.current

        embed = discord.Embed(title='Music Controller - Page 1/2', description=f'Now Playing:```\n{song.title}\n```',
                              colour=self.eq['colour'])
        embed.set_thumbnail(url=song.thumb)

        if self.PLAYER.next:
            sizedis = self.PLAYER.queue.qsize() + 1
        else:
            sizedis = self.PLAYER.queue.qsize()

        embed.add_field(name='Duration', value=str(datetime.timedelta(seconds=int(song.remaining))))
        embed.add_field(name='Video URL', value=f'[Click Here!]({song.web_url})')
        embed.add_field(name='Requested By', value=song.requester.mention)
        embed.add_field(name='Current DJ', value=self.dj.mention)
        embed.add_field(name='Queue Length', value=str(sizedis))
        embed.add_field(name='Player Restrictions', value=f'`{self.restrictions.name.upper()}`')
        embed.add_field(name='Volume', value=f'**`{int(self.volume * 100)}%`**')
        embed.add_field(name='Equalizer', value=f'**`{self.eq["name"].capitalize()}`**')
        # embed.set_footer(text='The Bot requires Manage Messages permissions for Page-2 controls to work.')

        if self.PLAYER.queue.qsize() > 0:
            if not self.PLAYER.next:
                ventries = self.PLAYER.queue.queue
            else:
                ventries = [self.PLAYER.next] + list(self.PLAYER.queue.queue)
            data = '\n'.join(f'**-** `{v.title[0:50]}{"..." if len(v.title) > 50 else ""}`\n{"-"*10}'
                             for v in islice(ventries, 0, 3, None))
            embed.add_field(name='Coming Up:', value=data)

        elif self.PLAYER.queue.qsize() == 0 and self.PLAYER.next:
            data = f'**-** `{self.PLAYER.next.title[0:50]}{"..." if len(self.PLAYER.next.title) > 50 else ""}' \
                   f'`\n{"-"*10}'
            embed.add_field(name='Coming Up:', value=data)

        if not await self.is_current_fresh(song.channel) and self.current_message:
            try:
                await self.current_message.delete()
            except discord.HTTPException:
                pass

            self.current_message = await song.channel.send(embed=embed)

        elif not self.current_message:
            self.current_message = await song.channel.send(embed=embed)
        else:
            return await self.current_message.edit(embed=embed, content=None)

        try:
            self.reaction_task.cancel()
        except Exception:
            pass

        self._updates = 0
        self.reaction_task = self.bot.loop.create_task(self.reaction_controller())

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
                if m.id == self.current_message.id:
                    return True
        except (discord.HTTPException, AttributeError):
            return False
        return False


class Music(metaclass=utils.MetaCog, thumbnail='https://i.imgur.com/8eJgtrh.png'):
    """Music commands"""

    __slots__ = ('bot', 'controllers')

    def __init__(self, bot):
        self.bot = bot
        self.controllers = {}

    def get_controller(self, ctx):
        try:
            player = self.controllers[ctx.guild.id]
        except KeyError:
            player = PlayerController(self.bot, ctx)
            self.controllers[ctx.guild.id] = player

        return player

    async def __skip(self, controller):
        if controller.PLAYER.state == controller.PLAYER.MIXING:
            return

        with controller.PLAYER._lock:
            controller.PLAYER.pause()

            if controller.PLAYER.next:
                controller.PLAYER.current = await eaudio.YTDLSource.copy_source(controller=controller,
                                                                                source=controller.PLAYER.next)
            else:
                controller.PLAYER.current = None

            controller.PLAYER.next = None
            controller.PLAYER.resume()
            controller.PLAYER.after(controller.PLAYER._current_error, controller.PLAYER.previous)

    async def attempt_update(self, controller, *, required=0):
        if not controller.is_safe():
            pass
        elif controller._updates > required:
            return self.bot.loop.create_task(controller.message_controller())

        controller._updates += 1

    async def vote_check(self, ctx, player, command, *, required):
        vcc = len(ctx.voice_client.channel.members) - 1
        votes = getattr(player, command + 's', None)

        if vcc < 3:
            votes.clear()
            return True
        else:
            votes.add(ctx.author.id)

            if len(votes) >= required:
                votes.clear()
                return True
        return False

    async def _del_msg(self, ctx):
        if not ctx.voice_client:
            return await ctx.delete_supress()

        controller = self.get_controller(ctx)
        if not controller.current_message:
            await ctx.delete_supress()
        elif controller.current_extras:
            pass
        elif not ctx.message.id == controller.current_message.id:
            await ctx.delete_supress()

    async def on_voice_state_update(self, member, before, after):
        if not member.guild.voice_client:
            return

        vc = member.guild.voice_client
        vcm = vc.channel.members

        try:
            controller = self.bot.get_cog('Music').controllers[member.guild.id]
        except KeyError:
            return

        if after.channel == vc.channel:
            controller.last_seen = None

            if controller.dj not in vcm:
                controller.dj = member
            return
        elif before.channel != vc.channel:
            return

        if (len(vcm) - 1) <= 0:
            controller.last_seen = time.time()
        elif controller.dj not in vcm:
            controller.dj = vcm[0]

    async def __local_check(self, ctx):
        if ctx.invoked_with == 'help':
            return True

        if not ctx.guild:
            await ctx.send('Music commands can not be used in DMs.')
            return False

        if not ctx.voice_client:
            return True

        try:
            controller = self.controllers[ctx.guild.id]
        except KeyError:
            return True

        if await ctx.hasperms(manage_guild=True, administrator=True):
            return True
        elif ctx.author == controller.dj:
            return True
        elif not ctx.author.voice:
            return False
        elif ctx.author.voice.mute or ctx.author.voice.deaf:
            return False

        if controller.restrictions.value == 4:
            return False
        elif controller.restrictions.value == 3:
            if ctx.command.name == 'play':
                return True
            return False
        elif controller.restrictions.value == 2 and ctx.command.name in controller.restricted_plus:
            return False
        elif controller.restrictions.value == 1 and ctx.command.name in controller.restricted:
            return False
        return True

    @commands.command(name='reactcontrol', cls=utils.EvieeCommand, hidden=True)
    async def react_control(self, ctx):
        """Dummy command for error handling in our player."""
        pass

    @commands.command(name='play', aliases=['sing'], cls=utils.EvieeCommand)
    async def music_play(self, ctx, *, search: str):
        """Search for and add a song to the queue for playback.

        Aliases
        ---------
            sing

        Parameters
        ------------
        search: [Required]
            The song to play. This could be a simple text based search, a YouTube ID or URL.
            Uses YTDL to search for and retrieve songs.

        Examples
        ----------
        <prefix>play <search>

            {ctx.prefix}play What is love?
            {ctx.prefix}play https://www.youtube.com/watch?v=XfR9iY5y94s
            {ctx.prefix}play dQw4w9WgXcQ
        """
        await self._del_msg(ctx)

        vc = ctx.voice_client
        if vc is None:
            try:
                await ctx.invoke(self.connect_)
            except Exception:
                return
        else:
            if ctx.author not in vc.channel.members:
                return await ctx.send(f'You must be in **{vc.channel}** to request songs.', delete_after=30)

        controller = self.get_controller(ctx)
        controller.requested_loads += 1
        await ctx.trigger_typing()

        controller.active_loads += 1
        try:
            source = await eaudio.YTDLSource.create_source(ctx=ctx, search=search, loop=self.bot.loop,
                                                           volume=controller.volume)
        except Exception as e:
            print(e)
            source = None
            exc = e
        finally:
            controller.active_loads -= 1

        if not source:
            return await ctx.send(f'There was an error while retrieving your song:\n```css\n[{exc}]\n```')

        await ctx.send(f'```ini\nAdded {source.title} to the queue.\n```', delete_after=15)
        controller.PLAYER.queue.put(source, block=False)
        await asyncio.sleep(1)

        if not controller.is_safe():
            print(2)
            return
        if controller.PLAYER.current:
            print(3)
            try:
                await controller.message_controller()
            except Exception as e:
                print(e)
        else:
            print(4)
            try:
                await controller.message_controller(source)
            except Exception as e:
                print(e)

    @commands.command(name='connect', aliases=['join'])
    async def connect_(self, ctx, *, channel: discord.VoiceChannel=None):
        """Connect to voice.

        Parameters
        ------------
        channel: discord.VoiceChannel [Optional]
            The channel to connect to. If a channel is not specified, an attempt to join the voice channel you are in
            will be made.

        This command also handles moving the bot to different channels.
        """
        if not channel:
            try:
                channel = ctx.author.voice.channel
            except AttributeError:
                raise \
                    eaudio.InvalidVoiceChannel('No channel to join. Please either specify a valid channel or join one.')

        vc = ctx.voice_client

        if vc:
            if vc.channel.id == channel.id:
                return
            try:
                await vc.move_to(channel)
            except asyncio.TimeoutError:
                raise eaudio.VoiceConnectionError(f'Moving to channel: <{channel}> timed out.')
        else:
            try:
                await channel.connect()
            except asyncio.TimeoutError:
                raise eaudio.VoiceConnectionError(f'Connecting to channel: <{channel}> timed out.')

    @commands.command(name='pause', cls=utils.EvieeCommand)
    @commands.cooldown(3, 60, commands.BucketType.user)
    async def music_pause(self, ctx):
        """Pause the currently playing song.

        Conditions
        ------------
        Not in Restricted Mode:
            If an admin or DJ has set the Player to Restricted, only the admins or DJ
            may use this command.

        Examples
        ----------
        <prefix>pause

            {ctx.prefix}pause
        """
        await self._del_msg(ctx)

        vc = ctx.voice_client
        if not vc:
            return

        req = math.ceil((len(ctx.voice_client.channel.members) - 1) / 2.5)

        if vc.is_paused():
            return
        if not vc.is_playing():
            return await ctx.send('I am not currently playing anything!', delete_after=30)

        if ctx.author not in vc.channel.members:
            return await ctx.send(f'You must be in: **{vc.channel}** to use this command.', delete_after=30)

        controller = self.get_controller(ctx)

        if await ctx.hasperms(manage_guild=True):
            await self.do_pause(controller)

            return await ctx.send(f'{ctx.author.mention} has paused the song as an admin.', delete_after=30)

        if ctx.author.id in controller.pauses:
            await ctx.send(f'{ctx.author.mention}, you have already voted to pause!', delete_after=15)
        elif await self.vote_check(ctx, controller, 'pause', required=req):
            await ctx.send(f'Vote `pause` passed! Pausing the song...', delete_after=20)
            await self.do_pause(controller)
        else:
            await ctx.send(f'{ctx.author.mention}, has voted to pause the song! **{req - len(controller.pauses)}**'
                           f' more votes needed!', delete_after=30)

    async def do_pause(self, controller):
        controller.PLAYER.pause()
        controller.pauses.clear()
        song = controller.PLAYER.current

        embed = discord.Embed(title='Music Controller - PAUSED!',
                              description=f'Now Paused:'
                                          f' ```\n{song.title}\n```',
                              colour=0xa5d8d8)
        embed.set_thumbnail(url=song.thumb)
        embed.add_field(name='Requested By', value=song.requester.mention)
        embed.add_field(name='Video URL', value=f'[Click Here!]({song.web_url})')
        embed.add_field(name='Duration', value='PAUSED!')
        embed.add_field(name='Queue Length', value='0')
        embed.add_field(name='Current DJ', value=controller.dj.mention, inline=False)
        embed.add_field(name='Player Mode', value=f'`{controller.restrictions.name.upper()}`')

        await controller.current_message.edit(embed=embed)

    @commands.command(name='resume', cls=utils.EvieeCommand)
    @commands.cooldown(2, 45, commands.BucketType.user)
    async def music_resume(self, ctx):
        """Resume the currently paused song.

        Conditions
        ------------
        Not in Restricted or Semi-Restricted Mode:
            If an admin or DJ has set the Player to either (Restricted or Semi-Restricted) only the DJ
            and the Admins may use this command.

        Examples
        ----------
        <prefix>resume

            {ctx.prefix}resume
        """
        await self._del_msg(ctx)

        vc = ctx.voice_client
        if not vc:
            return
        if not vc.is_paused():
            return

        controller = self.get_controller(ctx)
        controller.PLAYER.resume()

        if controller.is_safe():
            await controller.message_controller()

        await ctx.send(f'{ctx.author.mention} has resumed the song!', delete_after=30)

    @commands.command(name='skip', cls=utils.EvieeCommand)
    @commands.cooldown(4, 60, commands.BucketType.user)
    async def music_skip(self, ctx):
        """Skips the currently paused song.

        Conditions
        ------------
        Not in Restricted or Semi-Restricted Mode:
            If an admin or DJ has set the Player to either (Restricted or Semi-Restricted) only the DJ
            and the Admins may use this command.

        Examples
        ----------
        <prefix>skip

            {ctx.prefix}skip
        """
        await self._del_msg(ctx)

        vc = ctx.voice_client
        if not vc:
            return

        req = math.ceil((len(ctx.voice_client.channel.members) - 1) / 2.5)

        if ctx.author not in vc.channel.members:
            return await ctx.send(f'You must be in: **{vc.channel}** to use this command.', delete_after=30)

        controller = self.get_controller(ctx)

        while controller.state > 0:
            await asyncio.sleep(.1)

        if controller.PLAYER.state == controller.PLAYER.MIXING:
            return await ctx.send('The next song is already starting!', delete_after=15)

        if await ctx.hasperms(manage_guild=True):
            await self.__skip(controller)
            return await ctx.send(f'{ctx.author.mention} has skipped the song as an admin.', delete_after=30)

        if ctx.author.id in controller.skips:
            await ctx.send(f'{ctx.author.mention}, you have already voted to skip!', delete_after=15)
        elif await self.vote_check(ctx, controller, 'skip', required=req):
            await ctx.send(f'Vote skip passed! Skipping the song...', delete_after=20)
            await self.__skip(controller)
        else:
            await ctx.send(f'{ctx.author.mention}, has voted to skip the song! **{req - len(controller.skips)}**'
                           f' more votes needed!', delete_after=30)

    @commands.command(name='stop', cls=utils.EvieeCommand)
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def music_stop(self, ctx):
        """Kills the player and clears your queue.

        Conditions
        ------------
        Not in Restricted or Semi-Restricted Mode:
            If an admin or DJ has set the Player to either (Restricted or Semi-Restricted) only the DJ
            and the Admins may use this command.

        Not more than 1 member in Voice:
            If there are more than one members in the current voice channel, (excluding the bot)
            this command can only be used by Admins or the DJ.

        Examples
        ----------
        <prefix>stop

            {ctx.prefix}stop
        """
        await self._del_msg(ctx)
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            # Could be indicative of a failed attempt previously
            try:
                await vc.disconnect(force=True)
            except Exception:
                return

        controller = self.get_controller(ctx)

        if not await ctx.hasperms(manage_guild=True) and controller.dj.id != ctx.author.id:
            if len(vc.channel.members) > 2:
                return

        controller.PLAYER.stop()

    @commands.command(name='shuffle', aliases=['mix'], cls=utils.EvieeCommand)
    @commands.cooldown(2, 60, commands.BucketType.guild)
    async def music_shuffle(self, ctx):
        """Shuffle the current playlist around.

        Aliases
        ---------
            mix

        Examples
        ----------
        <prefix>shuffle

            {ctx.prefix}shuffle
            {ctx.prefix}mix

        """
        await self._del_msg(ctx)
        vc = ctx.voice_client
        if not vc:
            return

        req = math.ceil((len(ctx.voice_client.channel.members) - 1) / 2.5)

        controller = self.get_controller(ctx)

        if controller.PLAYER.next:
            sizedis = controller.PLAYER.queue.qsize() + 1
        else:
            sizedis = controller.PLAYER.queue.qsize()

        if sizedis < 3:
            return await ctx.send('Please add more songs to the queue, before attempting to shuffle.', delete_after=15)

        if await ctx.hasperms(manage_guild=True):
            await self.do_shuffle(controller)
            return await ctx.send(f'{ctx.author.mention} has shuffled the playlist as an admin.', delete_after=30)

        if ctx.author.id in controller.shuffles:
            await ctx.send(f'{ctx.author.mention}, you have already voted to shuffle!', delete_after=15)
        elif await self.vote_check(ctx, controller, 'shuffle', required=req):
            await ctx.send(f'Vote shuffle passed! Shuffling the playlist...', delete_after=20)
            await self.do_shuffle(controller)
        else:
            await ctx.send(f'{ctx.author.mention}, has voted to shuffle the playlist! **{req - len(controller.skips)}**'
                           f' more votes needed!', delete_after=30)

    async def do_shuffle(self, controller):
        if controller.state > 0:
            return

        controller.state = controller.SHUFFLING

        while controller.PLAYER.state == controller.PLAYER.MIXING:
            await asyncio.sleep(.1)

        controller.PLAYER.queue.queue.append(controller.PLAYER.next)
        random.shuffle(controller.PLAYER.queue.queue)
        controller.PLAYER.next = None
        controller.state = controller.IDLE

        await self.attempt_update(controller, required=3)

    @commands.command(name='repeat', aliases=['replay'], cls=utils.EvieeCommand)
    @commands.cooldown(5, 60, commands.BucketType.user)
    async def music_repeat(self, ctx):
        """Repeat the currently playing song.

        Aliases
        ---------
            replay

        Examples
        ----------
        <prefix>repeat

            {ctx.prefix}repeat
            {ctx.prefix}replay

        """
        await self._del_msg(ctx)
        vc = ctx.voice_client
        if not vc:
            return

        req = math.ceil((len(ctx.voice_client.channel.members) - 1) / 2.5)

        controller = self.get_controller(ctx)

        if await ctx.hasperms(manage_guild=True):
            await self.do_repeat(controller)
            return await ctx.send(f'{ctx.author.mention} has repeated the song as an admin.', delete_after=30)

        if ctx.author.id in controller.shuffles:
            await ctx.send(f'{ctx.author.mention}, you have already voted to repeat!', delete_after=15)
        elif await self.vote_check(ctx, controller, 'repeat', required=req):
            await ctx.send(f'Vote repeat passed! Repeating the song...', delete_after=20)
            await self.do_repeat(controller)
        else:
            await ctx.send(f'{ctx.author.mention}, has voted to repeat the song! **{req - len(controller.skips)}**'
                           f' more votes needed!', delete_after=30)

    async def do_repeat(self, controller):
        print('Repeat - 1')
        if controller.state > 0:
            return
        print('Repeat - 2')

        controller.state = controller.SHUFFLING
        while controller.PLAYER.state == controller.PLAYER.MIXING:
            await asyncio.sleep(.1)

        print('Repeat - 3')

        if controller.PLAYER.next:
            controller.PLAYER.queue.queue.appendleft(controller.PLAYER.next)

        print('Repeat - 4')

        if not controller.PLAYER.current:
            to_get = getattr(controller.PLAYER, 'previous', None)
        else:
            to_get = getattr(controller.PLAYER, 'current', None)

        print('Repeat - 5')

        if not to_get:
            return

        print('Repeat - 6')

        try:
            source = await eaudio.YTDLSource.copy_source(controller=controller, source=to_get)
        except Exception as e:
            print(e)

        print('Repeat - 7')

        if not controller.PLAYER.current:
            controller.PLAYER.current = source
        else:
            controller.PLAYER.next = source

        print('Repeat - 8')
        controller.state = controller.IDLE
        await self.attempt_update(controller, required=0)

    @commands.command(name='volume', aliases=['vol'], cls=utils.EvieeCommand)
    @commands.cooldown(4, 60, commands.BucketType.guild)
    async def music_volume(self, ctx, volume: int):
        """Alters the current player volume.

        Aliases
        ---------
            vol

        Parameters
        ------------
        volume: int
            A value between 1 and 100 to use to adjust the volume on the player.

        Conditions
        ------------
        Not in Restricted or Semi-Restricted Mode:
            If an admin or DJ has set the Player to either (Restricted or Semi-Restricted) only the DJ
            and the Admins may use this command.

        Not more than 1 member in Voice:
            If there are more than one members in the current voice channel, (excluding the bot)
            this command can only be used by Admins or the DJ.

        Examples
        ----------
        <prefix>volume <volume>

            {ctx.prefix}volume 10
            {ctx.prefix}volume 83
        """
        await self._del_msg(ctx)
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return

        controller = self.get_controller(ctx)

        if not await ctx.hasperms(manage_guild=True) and controller.dj.id != ctx.author.id:
            if len(vc.channel.members) > 2:
                return

        if not 0 < volume < 101:
            return await ctx.send('Please enter a value between 1 and 100.')

        controller = self.get_controller(ctx)
        adj = float(volume) / 100

        try:
            vc.source.volume = adj
        except AttributeError:
            pass

        controller.volume = adj
        await ctx.send(f'Changed player volume to: **{volume}%**')

        await self.attempt_update(controller, required=0)

    @commands.command(name='vol_down', hidden=True, cls=utils.EvieeCommand)
    @commands.cooldown(7, 30, commands.BucketType.user)
    async def decrease_volume(self, ctx):
        """Turn the Volume down."""
        vc = ctx.voice_client
        if not vc:
            return

        controller = self.get_controller(ctx)
        orig = int(controller.volume * 100)
        vol_in = int(math.ceil((orig - 10) / 10.0)) * 10
        vol = float(vol_in) / 100

        if vol < 0.1:
            return await ctx.send('**Minimum volume reached.**', delete_after=5)

        try:
            controller.PLAYER.current.volume = vol
            if controller.PLAYER.next:
                controller.PLAYER.next.volume = vol
        except AttributeError:
            pass

        controller.volume = vol

        await self.attempt_update(controller, required=3)

    @commands.command(name='vol_up', aliases=['vup', 'up'], hidden=True, cls=utils.EvieeCommand)
    @commands.cooldown(7, 30, commands.BucketType.user)
    async def increase_volume(self, ctx):
        """Turn the Volume Up!"""
        vc = ctx.voice_client
        if not vc:
            return

        controller = self.get_controller(ctx)
        orig = int(controller.volume * 100)
        vol_in = int(math.ceil((orig + 10) / 10.0)) * 10
        vol = float(vol_in) / 100

        if vol > 1.0:
            return await ctx.send('**Max volume reached.**', delete_after=5)

        try:
            controller.PLAYER.current.volume = vol
            if controller.PLAYER.next:
                controller.PLAYER.next.volume = vol
        except AttributeError:
            pass

        controller.volume = vol

        await self.attempt_update(controller, required=3)

    @commands.command(name='nowplaying', aliases=['np', 'now_playing', 'current', 'currentsong'], cls=utils.EvieeCommand)
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def music_now_playing(self, ctx):
        """Invoke the Player Controller and show various player information.

        Aliases
        ---------
            np
            current
            currentsong
            now_playing

        Conditions
        ------------
        Not in Restricted or Semi-Restricted Mode:
            If an admin or DJ has set the Player to either (Restricted or Semi-Restricted) only the DJ
            and the Admins may use this command.

        Examples
        ----------
        <prefix>nowplaying
        <prefix>np

            {ctx.prefix}nowplaying
            {ctx.prefix}np
            {ctx.prefix}currentsong
        """
        vc = ctx.voice_client
        if not vc:
            return

        controller = self.get_controller(ctx)
        if not controller.PLAYER.current:
            return await ctx.send('I am not currently playing anything!', delete_after=30)

        await self.attempt_update(controller, required=0)

    @commands.command(name='queue', aliases=['q', 'que'], cls=utils.EvieeCommand)
    @commands.cooldown(3, 60, commands.BucketType.guild)
    async def music_queue(self, ctx):
        """Display upcoming songs in the playlist.

        Aliases
        ---------
            q
            que

        Examples
        ----------
        <prefix>queue
        <prefix>q

            {ctx.prefix}queue
            {ctx.prefix}q
        """
        vc = ctx.guild.voice_client
        if not vc:
            return

        controller = self.get_controller(ctx)
        _next = controller.PLAYER.next
        if _next:
            q = [s.title for s in [_next] + list(controller.PLAYER.queue.queue)]
        else:
            q = []

        if len(q) <= 0:
            return await ctx.send(f'```css\n[No songs currently queued.]\n```', delete_after=10)

        await ctx.paginate(entries=q, colour=controller.eq['colour'], title='Upcoming (10 per Page) - ',
                           prepend='**-** ', fmt='`')

    @commands.command(name='eq', aliases=['equalizer', 'effect'], cls=utils.EvieeCommand)
    @commands.cooldown(4, 90, commands.BucketType.user)
    @utils.has_perms_or_dj(manage_guild=True)
    async def music_eq(self, ctx, *, equalizer: str):
        """Alter the EQ of the player, with a selection of presets.

        Aliases
        ---------
            equalizer
            effect

        Parameters
        ------------
        equalizer: [Required]
            The EQ to set the player to. Could be either Rock, Boost, Nightcore or Flat.

        Examples
        ----------
        <prefix>eq <equalizer>

            {ctx.prefix}eq rock
            {ctx.prefix}equalizer boost
        """
        await self._del_msg(ctx)

        vc = ctx.voice_client
        if not vc:
            return

        controller = self.get_controller(ctx)
        if not controller.PLAYER.current:
            return

        equalizer = equalizer.upper()
        previous = controller.eq
        controller.eq = getattr(eaudio.EQS, equalizer, None)

        if not controller.eq:
            controller.eq = eaudio.EQS.FLAT
            return await ctx.send('Invalid Equalizer:\n```ini\nValid Equalizers:\n\n'
                                  '[Flat, Nightcore, Boost, Rock]\n```')

        if previous == controller.eq:
            return

        await self.do_equalizer(controller, previous)
        await ctx.send(f'The EQ is now **`{equalizer.capitalize()}`**.', delete_after=20)

    async def do_equalizer(self, controller, previous):
        with controller.PLAYER._lock:
            controller.PLAYER.pause()
            source = await eaudio.YTDLSource.edit_source(controller, controller.PLAYER.current, controller.eq,
                                                         previous)

            if controller.PLAYER.next:
                _next = await eaudio.YTDLSource.copy_source(controller, controller.PLAYER.next)
                controller.PLAYER.next.cleanup()
                controller.PLAYER.next = _next
            controller.PLAYER.current.cleanup()
            source.frames = controller.PLAYER.current.frames
            controller.PLAYER.current = source
            controller.PLAYER.resume()

            await self.attempt_update(controller, required=0)

    @commands.command(name='dj', cls=utils.AbstractorGroup, aliases=['force'], abstractors=['new'])
    async def _dj(self, ctx):
        """Commands for the DJ and Admins to manage the Player/Music."""
        pass

    @_dj.command(name='extras', aliases=['extra'], hidden=True)
    @utils.has_perms_or_dj(manage_guild=True)
    async def controller_extras_page(self, ctx):
        """Retrieve Extras controls for the PLayer..."""
        await self._del_msg(ctx)

        vc = ctx.voice_client
        if not vc:
            return

        controller = self.get_controller(ctx)
        self.bot.loop.create_task(controller.extras_message_controller())

    @_dj.command(name='information', hidden=True)
    @utils.has_perms_or_dj(manage_guild=True)
    async def controller_help(self, ctx):
        await self._del_msg(ctx)

        vc = ctx.voice_client
        if not vc:
            return

        cmd = self.bot.get_command('help')
        await ctx.invoke(cmd, 'dj mode')

    @_dj.command(name='new', aliases=['change', 'assign', 'swap'])
    @utils.has_perms_or_dj(manage_guild=True)
    async def dj_swap(self, ctx):
        """Swap the DJ."""
        await self._del_msg(ctx)

    @_dj.command(name='mode', aliases=['status', 'level', 'levels', 'modes'])
    @utils.has_perms_or_dj(manage_guild=True)
    async def dj_mode(self, ctx, *, level: int):
        """Set the player mode/level/status

        Aliases
        ---------
            status
            level

        Parameters
        ------------
        level: int
            The integer value representing the level to set the player to.
        [S]
        Modes/Levels
        -------
        All administrators and the DJ are exempt from these rules.

        0: Open
            This mode allows for all members to use the Player Controller and commands. Most of these commands
            still implement Cooldowns and initiate Vote Requests to avoid spam and disruptions.

        1: Semi-Restricted
            This mode restricts members to only being able to initiate pause, shuffle or repeat requests.
            All other commands (minus song requests) are blocked.

        2: Semi-Restricted+
            This mode has all the restrictions of Level 1(Semi-Restricted) plus it disallows any song requests.

        3: Restricted
            This mode restricts all commands and Player Controls (minus song requests),
            to being allowed only by Admins or the DJ.

        4: Restricted+
            This mode has all the restrictions of Level 3(Restricted) plus it disallows any song requests.
        [S]
        Examples
        ----------
        <prefix>dj mode <level>
        <prefix>dj level <level>

            {ctx.prefix}dj mode 1
            {ctx.prefix}dj level 4
            {ctx.prefix}force level 3
        """
        await self._del_msg(ctx)

        vc = ctx.voice_client
        if not vc:
            return

        controller = self.get_controller(ctx)

        try:
            controller.restrictions = eaudio.RestrictionStatus(level)
        except ValueError:
            return await ctx.send('Invalid Mode:\n```\nAdmins and the DJ are exempt from the following rules:\n\n'
                                  '0 = Open (Open to members to allow vote requests or use the Volume Control.)\n'
                                  '1 = Semi-Restricted (Members may only make vote requests to pause, shuffle'
                                  ' and repeat, with no Volume Controls.)\n'
                                  '2 = Restricted (Members may not use any player controls.'
                                  ' Song requests are still possible)\n'
                                  '3 = Restricted+ (The limitations of Restricted,'
                                  ' but members may not make song requests)```')

        await ctx.send(f'{ctx.author.mention} has set the player mode to: **`{controller.restrictions.name}`**',
                       delete_after=20)

        controller._updates += 1

    @_dj.command(name='pause')
    @utils.has_perms_or_dj(manage_guild=True)
    async def dj_pause(self, ctx):
        """Pause the player as a DJ or Admin.

        Similar to a standard pause with less restrictions.

        Examples
        ----------
        <prefix>dj pause

            {ctx.prefix}dj pause
        """
        await self._del_msg(ctx)
        vc = ctx.voice_client

        if not vc or not vc.is_playing():
            return
        if vc.is_paused():
            return

        controller = self.get_controller(ctx)

        controller.PLAYER.pause()
        controller.pauses.clear()

        await ctx.send(f'{ctx.author.mention} has paused the song as the DJ or Admin.', delete_after=30)

    @_dj.command(name='resume')
    @utils.has_perms_or_dj(manage_guild=True)
    async def dj_resume(self, ctx):
        """Resume the player from a paused state as a DJ or Admin.

        Similar to a standard resume with less restrictions.

        Examples
        ----------
        <prefix>dj resume

            {ctx.prefix}dj resume
        """
        await self._del_msg(ctx)
        vc = ctx.voice_client

        if not vc:
            return
        if not vc.is_paused():
            return

        controller = self.get_controller(ctx)
        controller.PLAYER.resume()
        controller.resumes.clear()

        await ctx.send(f'{ctx.author.mention} has resumed the song as the DJ or Admin.', delete_after=30)

    @_dj.command(name='skip')
    @utils.has_perms_or_dj(manage_guild=True)
    async def dj_skip(self, ctx):
        """Skip the currently playing song as a DJ or Admin.

        Similar to a standard skip with less restrictions.

        Examples
        ----------
        <prefix>dj skip

            {ctx.prefix}dj skip
        """
        await self._del_msg(ctx)

        vc = ctx.voice_client
        controller = self.get_controller(ctx)

        if not vc or not controller.PLAYER.current:
            return

        await self.__skip(controller)
        await ctx.send(f'{ctx.author.mention} has skipped the song as the DJ or Admin.', delete_after=30)

    @_dj.command(name='stop')
    @commands.cooldown(1, 30, commands.BucketType.user)
    @utils.has_perms_or_dj(manage_guild=True)
    async def dj_stop(self, ctx):
        """Stop the player as DJ or Admin

        Similar to a standard stop with less restrictions.

        Examples
        ----------
        <prefix>dj stop

            {ctx.prefix}dj stop
        """
        await self._del_msg(ctx)
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            # Could be indicative of a failed attempt previously
            try:
                await vc.disconnect(force=True)
            except Exception:
                return

        controller = self.get_controller(ctx)
        controller.PLAYER.stop()

    @_dj.command(name='shuffle')
    @commands.cooldown(3, 60, commands.BucketType.user)
    @utils.has_perms_or_dj(manage_guild=True)
    async def dj_shuffle(self, ctx):
        """Shuffle the playlist as a DJ or Admin.

        Similar to a standard shuffle with less restrictions.

        Examples
        ----------
        <prefix>dj shuffle

            {ctx.prefix}dj shuffle
        """
        await self._del_msg(ctx)
        vc = ctx.voice_client
        if not vc:
            return

        controller = self.get_controller(ctx)

        if controller.PLAYER.next:
            sizedis = controller.PLAYER.queue.qsize() + 1
        else:
            sizedis = controller.PLAYER.queue.qsize()

        if sizedis < 3:
            return await ctx.send('Please add more songs to the queue, before attempting to shuffle.', delete_after=15)

        await self.do_shuffle(controller)
        await ctx.send(f'{ctx.author.mention} has shuffled the playlist as the DJ or Admin.', delete_after=15)

    @_dj.command(name='repeat')
    @commands.cooldown(5, 60, commands.BucketType.user)
    @utils.has_perms_or_dj(manage_guild=True)
    async def dj_repeat(self, ctx):
        """Repeat the current song as the DJ or Admin.

        Similar to a standard repeat with less restrictions.

        Examples
        ----------
        <prefix>dj repeat

            {ctx.prefix}dj repeat
        """
        await self._del_msg(ctx)
        vc = ctx.voice_client
        if not vc:
            return

        controller = self.get_controller(ctx)

        try:
            await self.do_repeat(controller)
        except Exception as e:
            controller.state = controller.IDLE

        await ctx.send(f'{ctx.author.mention} has repeated the song as the DJ or Admin.', delete_after=15)
