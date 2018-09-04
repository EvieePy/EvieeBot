import discord
from discord.ext import commands

import asyncio
import asyncpg
import async_timeout
import base64
import datetime
import itertools
import logging
import math
import random
import re
import time

import utils

logger = logging.getLogger('eviee')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='eviee.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

rurl = re.compile('https?:\/\/(?:www\.)?.+')
surl = re.compile('https:\/\/open.spotify.com?.+playlist\/([a-zA-Z0-9]+)')


class Track:

    def __init__(self, id_, info, ctx, query=None):
        self.ctx = ctx
        self.id = id_
        self.requester = ctx.author
        self.channel = ctx.channel
        self.message = ctx.message
        self.query = query

        self.title = info.get('title')
        self.ytid = info.get('identifier')
        self.length = info.get('length')
        self.thumb = f"https://img.youtube.com/vi/{self.ytid}/default.jpg"
        self.uri = info.get('uri')

        self.is_stream = info.get('isStream')
        self.dead = False

    def __str__(self):
        return self.title

    @property
    def is_dead(self):
        return self.dead


class MusicQueue(asyncio.Queue):

    def __init__(self, ctx):
        self.bot = ctx.bot
        self.guild_id = ctx.guild.id
        super(MusicQueue, self).__init__()

        self.next_event = asyncio.Event()
        self.controller_message = None
        self.controls = {'⏯': 'rp',
                         '⏹': 'stop',
                         '⏭': 'skip',
                         '🔀': 'shuffle',
                         '🔂': 'repeat',
                         '➕': 'vol_up',
                         '➖': 'vol_down',
                         'ℹ': 'queue',
                         '💟': 'favourites add',
                         '⚠': 'report'}
        self.current = None
        self.reaction_task = None
        self.dj = None
        self.last_seen = None
        self.updating = False
        self.update = False
        self.inactive = False
        self.playing = False

        self.pauses = set()
        self.resumes = set()
        self.stops = set()
        self.shuffles = set()
        self.skips = set()
        self.repeats = set()

        self.player_task = self.bot.loop.create_task(self.player_loop())
        self.updater_task = self.bot.loop.create_task(self.updater())

    def popindex(self, index: int):
        ls = list(self.entries)
        item = ls[index]

        del self.entries[index]

        return item

    @property
    def entries(self):
        return self._queue

    async def updater(self):
        while not self.bot.is_closed():
            if self.update and not self.updating:
                self.update = False
                await self.invoke_controller()

            await asyncio.sleep(10)

    async def player_loop(self):
        """Loop which handles track callback with events."""
        await self.bot.wait_until_ready()

        while True:
            logger.debug('Loop: Beginning Cycle')

            self.locked = True

            try:
                with async_timeout.timeout(300):
                    track = await self.get()
            except asyncio.TimeoutError:
                self.inactive = True
                continue

            self.inactive = False
            logger.debug('Loop: Retrieved track')

            if track.is_dead:  # Empty dead tracks
                logger.debug('Loop: Track was dead, restarting cycle')
                continue

            if not track.id:
                songs = await self.bot.lavalink.query(f'ytsearch:{track.query}')
                
                if not songs:
                    continue
                elif not songs['tracks']:
                    continue

                try:
                    song = songs['tracks'][0]
                    track = Track(id_=song['track'], info=song['info'], ctx=track.ctx)
                except Exception as e:
                    continue

            self.current = track

            await self.invoke_controller()
            logger.debug('Loop: Invoked controller')

            player = self.bot.lavalink.get_player(self.guild_id)
            if not player.track_callback:
                logger.info('Loop: Setting callback function and initial volume')
                await player.set_volume(40)
                player.track_callback = self.callback

            while not player.connected:
                await asyncio.sleep(0.1)

            self.playing = True
            await player.play(track.id)
            logger.info('Loop: Initiated Play')

            while self.locked:
                await asyncio.sleep(0.1)
                
            self.playing = False
            logger.debug('Loop: Event was set')

            self.pauses.clear()
            self.resumes.clear()
            self.stops.clear()
            self.shuffles.clear()
            self.skips.clear()
            self.repeats.clear()

    def callback(self, player, reason):
        logger.info(f'Callback: {reason}')

        if reason == 'STOPPED' or reason == 'FINISHED':
            logger.info(f'Callback: Event set')
            self.locked = False

    async def invoke_controller(self, track: Track = None):
        if not track:
            track = self.current

        self.updating = True

        player = self.bot.lavalink.get_player(self.guild_id)

        embed = discord.Embed(title='Music Controller (Beta)', description=f'Now Playing:```\n{track.title}\n```',
                              colour=0x38fab3)
        embed.set_thumbnail(url=track.thumb)

        if track.is_stream:
            embed.add_field(name='Duration', value='🔴`Streaming`')
        else:
            embed.add_field(name='Duration', value=str(datetime.timedelta(milliseconds=int(track.length))))
        embed.add_field(name='Video URL', value=f'[Click Here!]({track.uri})')
        embed.add_field(name='Requested By', value=track.requester.mention)
        embed.add_field(name='Current DJ', value=self.dj.mention)
        embed.add_field(name='Queue Length', value=str(len(self.entries)))
        # embed.add_field(name='Player Restrictions', value=f'`None`')
        embed.add_field(name='Volume', value=f'**`{player.volume}%`**')
        embed.set_footer(text='ℹ - Queue, 💟 - Add to playlist, ⚠ - Report/Feedback')

        if len(self.entries) > 0:
            data = '\n'.join(f'**-** `{t.title[0:45]}{"..." if len(t.title) > 45 else ""}`\n{"-"*10}'
                             for t in itertools.islice([e for e in self.entries if not e.is_dead], 0, 3, None))
            embed.add_field(name='Coming Up:', value=data, inline=False)

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
        player = self.bot.lavalink.get_player(self.guild_id)

        def check(r, u):
            if not self.controller_message:
                return False
            elif str(r) not in self.controls.keys():
                return False
            elif u.id == self.bot.user.id or r.message.id != self.controller_message.id:
                return False
            elif u not in player.channel.members:
                return False
            return True

        while self.controller_message:
            print('Reaction Controller: Beginning Cycle')
            if player.channel is None:
                print('Reaction Controller: Breaking Cycle')
                return self.reaction_task.cancel()

            print('Reaction Controller: Waiting for Reaction')
            react, user = await self.bot.wait_for('reaction_add', check=check)
            print('Reaction Controller: Recognized Reaction')
            control = self.controls.get(str(react))

            if control == 'rp':
                if player.paused:
                    control = 'resume'
                else:
                    control = 'pause'

            print(f'CONTROL: {control}')

            try:
                await self.controller_message.remove_reaction(react, user)
            except discord.HTTPException:
                pass

            """cmd = self.bot.get_command(f'{"dj " if user.id == self.dj.id else ""}{control}')\
                or self.bot.get_command(control)"""
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


class Music(metaclass=utils.MetaCog, thumbnail='https://i.imgur.com/8eJgtrh.png', colour=0x38fab3):
    """Music related commands, using Lavalink with Youtube and Spotify playlist support."""

    def __init__(self, bot):
        self.bot = bot
        self.queues = {}

        self.bot.loop.create_task(self.inactivity_check())
        self.bot.loop.create_task(self.refresh_token())

    @property
    def webhook(self):
        config = self.bot._config

        wh_id = config.get('WH', 'f_id')
        wh_token = config.get('WH', 'f_key')
        hook = discord.Webhook.partial(id=wh_id, token=wh_token, adapter=discord.AsyncWebhookAdapter(self.bot.session))
        return hook

    @utils.backoff_loop()
    async def inactivity_check(self):
        await self.bot.wait_until_ready()

        await asyncio.sleep(20)

        inactive = []
        for q in self.queues.values():
            if q.inactive:
                inactive.append(q)

        for q in inactive:
            print(f'Inactivty Check: Inactive Queue {q.guild_id}')
            await q.destroy_controller()

            try:
                q.player_task.cancel()
            except Exception:
                pass

            try:
                q.updater_task.cancel()
            except Exception:
                pass

            try:
                await q.player.disconnect()
            except AttributeError:
                pass

            self.queues.pop(q.guild_id)
            self.bot.lavalink._players.pop(q.guild_id)

    async def delete_message(self, ctx):
        queue = self.get_queue(ctx)
        if not queue.controller_message:
            pass
        elif ctx.message.id == queue.controller_message.id:
            return

        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

    async def __local_check(self, ctx):
        if ctx.invoked_with == 'help':
            return True

        if not ctx.guild:
            await ctx.send('Music commands can not be used in DMs!')
            return False

        try:
            self.queues[ctx.guild.id]
        except KeyError:
            return True

        player = self.get_player(ctx.guild)

        if ctx.invoked_with == 'connect' and not player.connected:
            return True
        elif ctx.invoked_with == 'play' and not player.connected:
            return True
        elif ctx.invoked_with == 'queue' and player.connected:
            return True

        if ctx.author not in player.channel.members:
            return False
        return True

    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return

        player = self.get_player(member.guild)

        if not player or not player.connected:
            return

        vcm = player.channel.members

        try:
            queue = self.queues[member.guild.id]
        except KeyError:
            return

        if after.channel == player.channel:
            queue.last_seen = None

            if queue.dj not in vcm:
                queue.dj = member
            return
        elif before.channel != player.channel:
            return

        if (len(vcm) - 1) <= 0:
            queue.last_seen = time.time()
        elif queue.dj not in vcm:
            for mem in vcm:
                if mem.bot:
                    continue
                else:
                    queue.dj = mem
                    break

    def required(self, player):
        return math.ceil((len(player.channel.members) - 1) / 2.5)

    def get_queue(self, ctx):
        try:
            queue = self.queues[ctx.guild.id]
        except KeyError:
            queue = MusicQueue(ctx)
            self.queues[ctx.guild.id] = queue

        return queue

    def get_player(self, guild):
        player = self.bot.lavalink.get_player(guild.id)

        return player

    async def has_perms(self, ctx, **perms):
        queue = self.get_queue(ctx)

        if ctx.author.id == queue.dj.id:
            return True

        ch = ctx.channel
        permissions = ch.permissions_for(ctx.author)

        missing = [perm for perm, value in perms.items() if getattr(permissions, perm, None) != value]

        if not missing:
            return True

        return False

    async def vote_check(self, ctx, command: str):
        player = self.get_player(ctx.guild)
        queue = self.get_queue(ctx)

        vcc = len(player.channel.members) - 1
        votes = getattr(queue, command + 's', None)

        if vcc < 3:
            votes.clear()
            return True
        else:
            votes.add(ctx.author.id)

            if len(votes) >= self.required(player):
                votes.clear()
                return True
        return False

    async def do_vote(self, ctx, queue, command: str):
        attr = getattr(queue, command + 's', None)
        player = self.get_player(ctx.guild)

        if ctx.author.id in attr:
            await ctx.send(f'{ctx.author.mention}, you have already voted to {command}!', delete_after=15)
        elif await self.vote_check(ctx, command):
            await ctx.send(f'Vote request for {command} passed!', delete_after=20)
            to_do = getattr(self, f'do_{command}')
            await to_do(ctx)
        else:
            await ctx.send(f'{ctx.author.mention}, has voted to {command} the song!'
                           f' **{self.required(player) - len(attr)}** more votes needed!', delete_after=45)

    @commands.command(name='reactcontrol', hidden=True, cls=utils.EvieeCommand)
    async def react_control(self, ctx):
        """Dummy command for error handling in our player."""
        pass

    @commands.command(name='connect', aliases=['join', 'move'], cls=utils.EvieeCommand)
    async def connect_(self, ctx, *, channel: discord.VoiceChannel = None):
        """Connect to voice.

        Parameters
        ------------
        channel: discord.VoiceChannel [Optional]
            The channel to connect to. If a channel is not specified, an attempt to join the voice channel you are in
            will be made.

        This command also handles moving the bot to different channels.
        """
        await self.delete_message(ctx)

        player = self.get_player(ctx.guild)

        if player.connected:
            return

        if not channel:
            try:
                channel = ctx.author.voice.channel
            except AttributeError:
                raise utils.EvieeBaseException('No channel to join. Please either specify a valid channel or join one.')

        await player.connect(channel.id)

    async def refresh_token(self):
        auth = base64.b64encode(
            f'd20f6b5146b6493fb1133183a6eec6b3:{self.bot._config.get("SPOTIFY", "secret")}'.encode())
        headers = {'Authorization': f'Basic {auth.decode()}',
                   'Content-Type': "application/x-www-form-urlencoded"}

        while True:
            async with self.bot.session.post('https://accounts.spotify.com/api/token', headers=headers,
                                             data='grant_type=client_credentials') as resp:
                value = await resp.json()

                self.bot._config.set('SPOTIFY', 'value', value['access_token'])
                with open('config.ini', 'w') as configfile:
                    self.bot._config.write(configfile)

            await asyncio.sleep(3500)

    async def get_spotify(self, id_):
        headers = {f'Accept': 'application/json', 'Content-Type': 'application/json',
                   'Authorization': f'Bearer {self.bot._config.get("SPOTIFY", "value")}'}

        async with self.bot.session.get(f'https://api.spotify.com/v1/playlists/{id_}/tracks', headers=headers) as resp:
            data = await resp.json()

        return data

    @commands.command(name='play', aliases=['sing'], cls=utils.EvieeCommand)
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def play_(self, ctx, *, query: str):
        """Queue a song or playlist for playback.

        Aliases
        ---------
            sing

        Parameters
        ------------
        query: simple, URL [Required]
            The query to search for a song. This could be a simple search term or a valid URL.
            e.g Youtube URL or Spotify Playlist URL.

        Examples
        ----------
        <prefix>play <query>

            {ctx.prefix}play What is love?
            {ctx.prefix}play https://www.youtube.com/watch?v=XfR9iY5y94s
        """
        await ctx.invoke(self.connect_)
        query = query.strip('<>')

        player = self.get_player(ctx.guild)

        if not player.connected:
            return await ctx.send('Bot is not connected to voice. Please join a voice channel to play music.')

        queue = self.get_queue(ctx)

        if len(queue.entries) >= 1000:
            return await ctx.send('You have queued the maximum amount of songs!')

        if not queue.dj:
            queue.dj = ctx.author

        try:
            match = re.match(surl, query)
            spotify = match.group(1)
            print(spotify)
        except AttributeError:
            sdata = None
        else:
            sdata = await self.get_spotify(spotify)

        if sdata:
            data = sdata['items']

            for track in data:
                if not track['track']['type'] == 'track':
                    continue

                query = f'{track["track"]["name"]} - {track["track"]["artists"][0]["name"]}'

                if len(queue.entries) >= 1000:
                    break

                await queue.put(Track(id_=None, info={'title': query}, ctx=ctx, query=query))

            if queue.controller_message and not player.stopped:
                await queue.invoke_controller()

            return await ctx.send('Successfully added your Spotify playlist to the queue.', delete_after=20)

        if not rurl.match(query):
            query = f'ytsearch:{query}'

        print(f'Play: Query = {query}')

        songs = await self.bot.lavalink.query(query)
        print(f'Play: {songs}')
        if not songs or not songs['tracks']:
            return await ctx.send('No songs were found with that query. Try again.')

        if songs['playlistInfo']:
            for index, song in enumerate(songs['tracks'], 1):
                if len(queue.entries) >= 1000:
                    break
                await queue.put(Track(id_=song['track'], info=song['info'], ctx=ctx))

            await ctx.send(f'```ini\nAdded the playlist {songs["playlistInfo"]["name"]}'
                           f' with {index} songs to the queue.\n```')
        else:
            song = songs['tracks'][0]

            await ctx.send(f'```ini\nAdded {song["info"]["title"]} to the Queue\n```', delete_after=15)
            await queue.put(Track(id_=song['track'], info=song['info'], ctx=ctx))

        if queue.controller_message:
            await queue.invoke_controller()

    @commands.command(name='now_playing', aliases=['np', 'current', 'currentsong'], cls=utils.EvieeCommand)
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def now_playing(self, ctx):
        """Invoke the player controller.

        Aliases
        ---------
            np
            current
            currentsong

        Examples
        ----------
        <prefix>now_playing

            {ctx.prefix}np

        The player controller contains various information about the current and upcoming songs.
        """
        await self.delete_message(ctx)
        player = self.get_player(ctx.guild)

        if not player.connected:
            return

        queue = self.get_queue(ctx)
        if queue.updating:
            return

        await queue.invoke_controller()

    @commands.command(name='pause', cls=utils.EvieeCommand)
    async def pause_(self, ctx):
        """Pause the currently playing song.

        Examples
        ----------
        <prefix>pause

            {ctx.prefix}pause
        """
        player = self.get_player(ctx.guild)

        if not player.connected:
            await ctx.send('I am not currently connected to voice!')

        if player.paused:
            return

        if await self.has_perms(ctx, manage_guild=True):
            await ctx.send(f'{ctx.author.mention} has paused the song as an admin or DJ.', delete_after=25)
            return await self.do_pause(ctx)

        queue = self.get_queue(ctx)
        await self.do_vote(ctx, queue, 'pause')

    async def do_pause(self, ctx):
        player = self.get_player(ctx.guild)
        await player.set_pause(True)

    @commands.command(name='resume', cls=utils.EvieeCommand)
    async def resume_(self, ctx):
        """Resume a currently paused song.

        Examples
        ----------
        <prefix>resume

            {ctx.prefix}resume
        """
        player = self.get_player(ctx.guild)

        if not player.connected:
            await ctx.send('I am not currently connected to voice!')

        if not player.paused or player.stopped:
            return

        if await self.has_perms(ctx, manage_guild=True):
            await ctx.send(f'{ctx.author.mention} has resumed the song as an admin or DJ.', delete_after=25)
            return await self.do_resume(ctx)

        queue = self.get_queue(ctx)
        await self.do_vote(ctx, queue, 'resume')

    async def do_resume(self, ctx):
        player = self.get_player(ctx.guild)
        await player.set_pause(False)

    @commands.command(name='skip', cls=utils.EvieeCommand)
    @commands.cooldown(5, 10, commands.BucketType.user)
    async def skip_(self, ctx):
        """Skip the current song.

        Examples
        ----------
        <prefix>skip

            {ctx.prefix}skip
        """
        player = self.get_player(ctx.guild)

        if not player.connected:
            return await ctx.send('I am not currently connected to voice!')

        if await self.has_perms(ctx, manage_guild=True):
            await ctx.send(f'{ctx.author.mention} has skipped the song as an admin or DJ.', delete_after=25)
            return await self.do_skip(ctx)

        queue = self.get_queue(ctx)
        await self.do_vote(ctx, queue, 'skip')

    async def do_skip(self, ctx):
        player = self.get_player(ctx.guild)

        await player.stop()

    @commands.command(name='stop', cls=utils.EvieeCommand)
    @commands.cooldown(2, 30, commands.BucketType.guild)
    async def stop_(self, ctx):
        """Stop the player, disconnect and clear the queue.

        Examples
        ----------
        <prefix>stop

            {ctx.prefix}stop
        """
        await self.delete_message(ctx)
        player = self.get_player(ctx.guild)

        if not player.connected:
            return await ctx.send('I am not currently connected to voice!')

        if await self.has_perms(ctx, manage_guild=True):
            await ctx.send(f'{ctx.author.mention} has stopped the player as an admin or DJ.', delete_after=25)
            return await self.do_stop(ctx)

        queue = self.get_queue(ctx)
        await self.do_vote(ctx, queue, 'stop')

    async def do_stop(self, ctx):
        queue = self.get_queue(ctx)
        player = self.get_player(ctx.guild)

        await queue.destroy_controller()

        try:
            queue.player_task.cancel()
        except Exception:
            pass

        try:
            queue.updater_task.cancel()
        except Exception:
            pass

        self.queues.pop(ctx.guild.id)

        await player.disconnect()
        self.bot.lavalink._players.pop(ctx.guild.id)

    @commands.command(name='volume', aliases=['vol'], cls=utils.EvieeCommand)
    @commands.cooldown(1, 2, commands.BucketType.guild)
    async def volume_(self, ctx, *, value: int):
        """Change the player volume.

        Aliases
        ---------
            vol

        Parameters
        ------------
        value: [Required]
            The volume level you would like to set. This can be a number between 1 and 100.

        Examples
        ----------
        <prefix>volume <value>

            {ctx.prefix}volume 50
        """
        await self.delete_message(ctx)
        player = self.get_player(ctx.guild)

        if not player.connected:
            return await ctx.send('I am not currently connected to voice!')

        if not 0 < value < 101:
            return await ctx.send('Please enter a value between 1 and 100.')

        queue = self.get_queue(ctx)

        if not await self.has_perms(ctx, manage_guild=True) and queue.dj.id != ctx.author.id:
            if (len(player.channel.members) - 1) > 2:
                return

        await player.set_volume(value)
        await ctx.send(f'Set the volume to **{value}**%', delete_after=7)

        if not queue.updating and not queue.update:
            await queue.invoke_controller()

    @commands.command(name='queue', aliases=['q', 'que'], cls=utils.EvieeCommand)
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def queue_(self, ctx):
        """Retrieve a list of currently queued songs.

        Aliases
        ---------
            que
            q

        Examples
        ----------
        <prefix>queue

            {ctx.prefix}queue
            {ctx.prefix}q
        """
        await self.delete_message(ctx)
        player = self.get_player(ctx.guild)

        if not player.connected:
            return await ctx.send('I am not currently connected to voice!')

        queue = self.get_queue(ctx)

        entries = [f'{i} - [{e.title}]({e.uri})' if not e.is_dead else f'**{i} -** ~~{e.title}~~'
                   for i, e in enumerate(queue.entries, 1)]

        if not entries:
            return await ctx.send('```\nNo more songs in the Queue!\n```', delete_after=15)

        await ctx.paginate(title=f'Upcoming({len(entries)} entries) Page', entries=entries)

    @commands.command(name='remove_songs', aliases=['removesongs', 'kill', 'delete', 'del'], cls=utils.EvieeCommand)
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def remove_songs_(self, ctx, *tracks):
        await self.delete_message(ctx)
        player = self.get_player(ctx.guild)

        if not player.connected:
            return await ctx.send('I am not currently connected to voice!')

        queue = self.get_queue(ctx)

        if not await self.has_perms(ctx, manage_guild=True):
            return await ctx.send('Only the DJ or an Admins may remove songs from the queue!')

        success = []

        for track in tracks:
            try:
                item = queue.entries[int(track) - 1]
                item.dead = True
            except IndexError:
                pass
            else:
                success.append(item.title)

        if not success:
            return await ctx.send('No songs were removed. Check you are removing valid tracks.')

        await ctx.paginate(title=f'Successfully removed ({len(success)}) songs... Page ', entries=success)

    @commands.command(name='shuffle', aliases=['mix'], cls=utils.EvieeCommand)
    @commands.cooldown(2, 10, commands.BucketType.user)
    async def shuffle_(self, ctx):
        """Shuffle the current queue.

        Aliases
        ---------
            mix

        Examples
        ----------
        <prefix>shuffle

            {ctx.prefix}shuffle
            {ctx.prefix}mix
        """
        await self.delete_message(ctx)
        player = self.get_player(ctx.guild)

        if not player.connected:
            return await ctx.send('I am not currently connected to voice!')

        queue = self.get_queue(ctx)

        if len(queue.entries) < 3:
            return await ctx.send('Please add more songs to the queue before trying to shuffle.', delete_after=10)

        if await self.has_perms(ctx, manage_guild=True):
            await ctx.send(f'{ctx.author.mention} has shuffled the playlist as an admin or DJ.', delete_after=25)
            return await self.do_shuffle(ctx)

        await self.do_vote(ctx, queue, 'shuffle')

    async def do_shuffle(self, ctx):
        queue = self.get_queue(ctx)
        random.shuffle(queue.entries)

        queue.update = True

    @commands.command(name='repeat', cls=utils.EvieeCommand)
    async def repeat_(self, ctx):
        """Repeat the currently playing song.

        Examples
        ----------
        <prefix>repeat

            {ctx.prefix}repeat
        """
        await self.delete_message(ctx)
        player = self.get_player(ctx.guild)

        if not player.connected:
            print('Not connected')
            return

        queue = self.get_queue(ctx)

        if await self.has_perms(ctx, manage_guild=True):
            await ctx.send(f'{ctx.author.mention} has repeated the song as an admin or DJ.', delete_after=25)
            return await self.do_repeat(ctx)

        await self.do_vote(ctx, queue, 'repeat')

    async def do_repeat(self, ctx):
        queue = self.get_queue(ctx)

        if not queue.entries:
            await queue.put(queue.current)
        else:
            queue.entries.appendleft(queue.current)

        print(queue.entries)

        queue.update = True

    @commands.command(name='vol_up', hidden=True, cls=utils.EvieeCommand)
    async def volume_up(self, ctx):
        player = self.get_player(ctx.guild)

        if not player.connected:
            return

        vol = int(math.ceil((player.volume + 10) / 10)) * 10

        if vol > 100:
            vol = 100
            await ctx.send('Maximum volume reached', delete_after=7)

        await player.set_volume(vol)

        queue = self.get_queue(ctx)
        queue.update = True

    @commands.command(name='vol_down', hidden=True, cls=utils.EvieeCommand)
    async def volume_down(self, ctx):
        player = self.get_player(ctx.guild)

        if not player.connected:
            return

        vol = int(math.ceil((player.volume - 10) / 10)) * 10

        if vol < 0:
            vol = 0
            await ctx.send('Player is currently muted', delete_after=10)

        await player.set_volume(vol)

        queue = self.get_queue(ctx)
        queue.update = True

    @commands.command(name='report', aliases=['bug'], cls=utils.EvieeCommand)
    @commands.cooldown(1, 180, commands.BucketType.user)
    async def report_(self, ctx):
        """Report a bug or send feedback related to the player.

        Aliases
        ---------
            bug
            feedback

        Parameters
        ------------
        prompt:
            A prompt will display asking you for information relating to the bug/feedback.

        Examples
        ----------
        <prefix>report

            {ctx.prefix}report
        """
        msg = await ctx.send('What would you like to report/feedback on?')

        def check(message):
            return message.author.id == ctx.author.id

        try:
            report = await self.bot.wait_for('message', check=check, timeout=180)
        except asyncio.TimeoutError:
            return await msg.delete()

        embed = discord.Embed(title=f'Bug Report/Feedback', colour=0xffae42,
                              description=f'```ini\n{report.content}\n```')
        embed.add_field(name='Guild', value=f'{ctx.guild.name}({ctx.guild.id})')
        embed.add_field(name='User', value=f'{ctx.author}({ctx.author.id})')
        embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar_url)
        embed.set_footer(text='Received ').timestamp = datetime.datetime.utcnow()
        embed.set_thumbnail(url=ctx.author.avatar_url)

        await self.webhook.send(embed=embed)

        await ctx.send('Thanks your report has been submitted! You can report again in 3 minutes.', delete_after=45)
        await msg.delete()

    @commands.command(name='favourites', aliases=['favorites', 'favourite', 'favorite', 'faves', 'fave'],
                      cls=utils.EvieeCommandGroup)
    async def favourites_(self, ctx):
        """View and edit your favourites.

        Aliases
        ---------
            favorites
            favorite
            favourite
            faves
            fave

        Sub-Commands
        --------------
            add
            import
            list

        Examples
        ----------
        <prefix>favourites <sub-command>

            {ctx.prefix}faves add (Adds the current song)
            {ctx.prefix}faves add What is love?
            {ctx.prefix}faves import (A valid Youtube Playlist URL)
        """
        await ctx.invoke(self.favourites_list)

    @favourites_.command(name='add')
    async def favourites_add(self, ctx, *, query: str = None):
        if query:
            query = query.strip('<>')

            if not rurl.match(query):
                query = f'ytsearch:{query}'

            songs = await self.bot.lavalink.query(query)
            if not songs or not songs['tracks']:
                return await ctx.send('No songs were found with that query. Please try again.')

            song = songs['tracks'][0]
            track = Track(ctx=ctx, id_=song['track'], info=song['info'])
        else:
            queue = self.get_queue(ctx)
            player = self.get_player(ctx.guild)

            if not queue.current:
                return await ctx.send('I am not currently playing anything!', delete_after=30)
            if not player.connected:
                return
            track = queue.current

        async with self.bot.pool.acquire() as conn:
            try:
                await conn.execute("""INSERT INTO playlists(uid, song_id, song_name)
                                      VALUES($1, $2, $3)""",
                                   ctx.author.id, track.id, track.title)
            except asyncpg.exceptions.UniqueViolationError:
                return await ctx.send(f'{ctx.author.mention}. This song is already in your favourites!',
                                      delete_after=30)
            else:
                return await ctx.send(f'Alright {ctx.author.mention}, I added `{track.title}` to your favourites.',
                                      delete_after=30)

    @favourites_.command(name='import', aliases=['playlist'])
    async def favourites_import(self, ctx, *, query: str):
        if query:
            query = query.strip('<>')

            if not rurl.match(query):
                query = f'ytsearch:{query}'

            songs = await self.bot.lavalink.query(query)
            if not songs or not songs['tracks']:
                return await ctx.send('No songs were found with that query. Please try again.')

            if not songs['playlistInfo']:
                return await ctx.send('This is not a valid playlist. Please try again!')

            results = []

            async with self.bot.pool.acquire() as conn:
                stmt = await conn.prepare(
                    """INSERT INTO playlists(uid, song_id, song_name) VALUES($1, $2, $3)
                        ON CONFLICT(uid, song_id) DO NOTHING RETURNING song_name""")

                async with conn.transaction():
                    for track in songs['tracks']:
                        async for record in stmt.cursor(ctx.author.id, track['track'], track['info']['title']):
                            results.append(record['song_name'])

            if not results:
                return await ctx.send('No songs could be added to your favourites. Perhaps they are already in there!',
                                      delete_after=30)

            await ctx.paginate(title=f'Added {len(results)} songs to your favourites | Page ',
                               entries=[f'{i} - {e}' for i, e in enumerate(results, 1)])

    @favourites_.command(name='list', aliases=['show'])
    async def favourites_list(self, ctx):
        async with self.bot.pool.acquire() as conn:
            results = await conn.fetch("""SELECT song_name FROM playlists WHERE uid IN($1)""", ctx.author.id)

        if not results:
            return await ctx.send('You do not currently have any songs in your favourites.')

        await ctx.paginate(title=f"{ctx.author.display_name}'s Favourites | Page",
                           entries=[f'{i} - {e["song_name"]}' for i, e in enumerate(results, 1)])
