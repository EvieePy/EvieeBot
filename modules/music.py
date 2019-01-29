import asyncio
import base64
import datetime
import discord
import humanize
import re
import math
import random
import sys
import time
import traceback
import wavelink
from discord.ext import commands
from typing import Union

from plugin.player import Player, Track
import utils

RURL = re.compile('https?://(?:www\.)?.+')
SURL = re.compile('https://open.spotify.com?.+playlist/([a-zA-Z0-9]+)')


class NotInChannel(Exception):
    def __init__(self, msg, *, channel):
        self.channel = channel


class NoChannel(Exception):
    pass


class Music(metaclass=utils.MetaCog, thumbnail='https://i.imgur.com/8eJgtrh.png', colour=0x38fab3):

    def __init__(self, bot: Union[commands.Bot, commands.AutoShardedBot]):
        self.bot = bot
        bot.wavelink = wavelink.Client(self.bot)

        bot.loop.create_task(self.refresh_token())
        bot.loop.create_task(self.initiate_nodes())

    async def initiate_nodes(self):
        nodes = {'MAIN': {'host': '51.158.68.132',
                          'port': 2333,
                          'rest_url': 'http://51.158.68.132:2333',
                          'password': self.bot._config.get('LL', 'value'),
                          'identifier': 'MAIN',
                          'region': 'us_central'}}

        for n in nodes.values():
            node = await self.bot.wavelink.initiate_node(host=n['host'],
                                                         port=n['port'],
                                                         rest_uri=n['rest_url'],
                                                         password=n['password'],
                                                         identifier=n['identifier'],
                                                         region=n['region'])

            node.set_hook(self.event_hook)

    def event_hook(self, event):
        """Our event hook. Dispatched when an event occurs on our Node."""
        print(event)
        if isinstance(event, (wavelink.TrackEnd, wavelink.TrackStuck, wavelink.TrackException)):
            event.player.next_event.set()

    def required(self, player, invoked_with):
        channel = self.bot.get_channel(int(player.channel_id))
        if invoked_with == 'stop':
            if len(channel.members) - 1 == 2:
                return 2

        return math.ceil((len(channel.members) - 1) / 2.5)

    async def has_perms(self, ctx, **perms):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        if ctx.author.id == player.dj.id:
            return True

        ch = ctx.channel
        permissions = ch.permissions_for(ctx.author)

        missing = [perm for perm, value in perms.items() if getattr(permissions, perm, None) != value]

        if not missing:
            return True

        return False

    async def vote_check(self, ctx, command: str):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        vcc = len(self.bot.get_channel(int(player.channel_id)).members) - 1
        votes = getattr(player, command + 's', None)

        if vcc < 3 and not ctx.invoked_with == 'stop':
            votes.clear()
            return True
        else:
            votes.add(ctx.author.id)

            if len(votes) >= self.required(player, ctx.invoked_with):
                votes.clear()
                return True
        return False

    async def do_vote(self, ctx, player, command: str):
        attr = getattr(player, command + 's', None)
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        if ctx.author.id in attr:
            await ctx.send(f'{ctx.author.mention}, you have already voted to {command}!', delete_after=15)
        elif await self.vote_check(ctx, command):
            await ctx.send(f'Vote request for {command} passed!', delete_after=20)
            to_do = getattr(self, f'do_{command}')
            await to_do(ctx)
        else:
            await ctx.send(f'{ctx.author.mention}, has voted to {command} the song!'
                           f' **{self.required(player, ctx.invoked_with) - len(attr)}** more votes needed!',
                           delete_after=45)

    async def __local_check(self, ctx):
        if ctx.invoked_with == 'help':
            return True

        if not ctx.guild:
            await ctx.send('Music commands can not be used in DMs!')
            return False

        try:
            self.bot.wavelink.players[ctx.guild.id]
        except KeyError:
            return True

        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        if ctx.invoked_with == 'connect' and not player.is_connected:
            return True
        elif ctx.invoked_with == '_info' and not player.is_connected:
            return True
        elif ctx.invoked_with == 'play' and not player.is_connected:
            return True
        elif ctx.invoked_with == 'queue' or ctx.invoked_with == 'q' and player.is_connected:
            return True

        if ctx.author not in self.bot.get_channel(int(player.channel_id)).members:
            await ctx.send(f'You must be in `{self.bot.get_channel(int(player.channel_id))}` to use the player.')
            return False
        return True

    async def __error(self, ctx, error):
        error = getattr(error, 'original', error)

        if isinstance(error, commands.CheckFailure):
            pass
        elif isinstance(error, NoChannel):
            await ctx.send('You must join a voice channel before starting music!')
        else:
            print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return

        player = self.bot.wavelink.get_player(member.guild.id, cls=Player)

        if not player or not player.is_connected:
            return

        vc = self.bot.get_channel(int(player.channel_id))

        if after.channel == vc:
            player.last_seen = None

            if player.dj not in vc.members:
                player.dj = member
            return
        elif before.channel != vc:
            return

        if (len(vc.members) - 1) <= 0:
            player.last_seen = time.time()
        elif player.dj not in vc.members:
            for mem in vc.members:
                if mem.bot:
                    continue
                else:
                    player.dj = mem
                    break

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

    @commands.command(name='connect', aliases=['join'])
    async def connect_(self, ctx, *, channel: discord.VoiceChannel = None):
        """Connect to voice.

        Parameters
        ------------
        channel: discord.VoiceChannel [Optional]
            The channel to connect to. If a channel is not specified, an attempt to join the voice channel you are in
            will be made.
        """
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

        if not channel:
            try:
                channel = ctx.author.voice.channel
            except AttributeError:
                raise NoChannel('No channel to join. Please either specify a valid channel or join one.')

        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        if player.is_connected:
            if ctx.author.voice.channel == ctx.guild.me.voice.channel:
                return

        await player.connect(channel.id)

    @commands.command(name='play', aliases=['sing'])
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
        await self.bot.wait_until_ready()

        await ctx.trigger_typing()

        await ctx.invoke(self.connect_)
        query = query.strip('<>')

        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        await asyncio.sleep(1)
        if not player.is_connected:
            return await ctx.send('Bot is not connected to voice. Please join a voice channel to play music.')

        if not player.dj:
            player.dj = ctx.author

        try:
            match = re.match(SURL, query)
            spotify = match.group(1)
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

                player.queue.put(Track(id_=None, info={'title': query}, ctx=ctx, query=query))

            if player.controller_message and player.is_playing:
                await player.invoke_controller()
            else:
                player.update = True

            return await ctx.send('Successfully added your Spotify playlist to the queue.', delete_after=20)

        if not RURL.match(query):
            query = f'ytsearch:{query}'

        songs = await self.bot.wavelink.get_tracks(query)
        if not songs:
            return await ctx.send('No songs were found with that query. Try again.')

        if isinstance(songs, wavelink.TrackPlaylist):
            for t in songs.tracks:
                player.queue.put(Track(t.id, t.info, ctx=ctx))

            await ctx.send(f'```ini\nAdded the playlist {songs.data["playlistInfo"]["name"]}'
                           f' with {len(songs.tracks)} songs to the queue.\n```')
        else:
            song = songs[0]

            await ctx.send(f'```ini\nAdded {song.title} to the Queue\n```', delete_after=15)
            player.queue.put(Track(id_=song.id, info=song.info, ctx=ctx))

        if player.controller_message and player.is_playing:
            await player.invoke_controller()

    @commands.command(name='reactcontrol', hidden=True)
    async def react_control(self, ctx):
        """Dummy command for error handling in our player."""
        pass

    @commands.command(name='now_playing', aliases=['np', 'current', 'currentsong'])
    @commands.cooldown(2, 15, commands.BucketType.user)
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
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)
        if not player:
            return

        if not player.is_connected:
            return

        if player.updating:
            return

        await player.invoke_controller()

    @commands.command(name='pause')
    async def pause_(self, ctx):
        """Pause the currently playing song.
        Examples
        ----------
        <prefix>pause
            {ctx.prefix}pause
        """
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)
        if not player:
            return

        if not player.is_connected:
            await ctx.send('I am not currently connected to voice!')

        if player.paused:
            return

        if await self.has_perms(ctx, manage_guild=True):
            await ctx.send(f'{ctx.author.mention} has paused the song as an admin or DJ.', delete_after=25)
            return await self.do_pause(ctx)

        await self.do_vote(ctx, player, 'pause')

    async def do_pause(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)
        await player.set_pause(True)

    @commands.command(name='resume')
    async def resume_(self, ctx):
        """Resume a currently paused song.
        Examples
        ----------
        <prefix>resume
            {ctx.prefix}resume
        """
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        if not player.is_connected:
            await ctx.send('I am not currently connected to voice!')

        if not player.paused:
            return

        if await self.has_perms(ctx, manage_guild=True):
            await ctx.send(f'{ctx.author.mention} has resumed the song as an admin or DJ.', delete_after=25)
            return await self.do_resume(ctx)

        await self.do_vote(ctx, player, 'resume')

    async def do_resume(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)
        await player.set_pause(False)

    @commands.command(name='skip')
    @commands.cooldown(5, 10, commands.BucketType.user)
    async def skip_(self, ctx):
        """Skip the current song.
        Examples
        ----------
        <prefix>skip
            {ctx.prefix}skip
        """
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        if not player.is_connected:
            return await ctx.send('I am not currently connected to voice!')

        if await self.has_perms(ctx, manage_guild=True):
            await ctx.send(f'{ctx.author.mention} has skipped the song as an admin or DJ.', delete_after=25)
            return await self.do_skip(ctx)

        if player.current.requester.id == ctx.author.id:
            await ctx.send(f'The requester {ctx.author.mention} has skipped the song.')
            return await self.do_skip(ctx)

        await self.do_vote(ctx, player, 'skip')

    async def do_skip(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        await player.stop()

    @commands.command(name='back')
    @commands.cooldown(5, 10, commands.BucketType.user)
    async def _back(self, ctx):
        """Go backwards in the Queue, and replay songs.
        Examples
        ----------
        <prefix>back
            {ctx.prefix}back
        """
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        if not player.is_connected:
            return await ctx.send('I am not currently connected to voice!')

        if await self.has_perms(ctx, manage_guild=True):
            await ctx.send(f'{ctx.author.mention} has gone back a song, as an admin or DJ.', delete_after=25)
            return await self.do_back(ctx)

        await self.do_vote(ctx, player, 'back')

    async def do_back(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        if int(player.position) / 1000 >= 7 or len(player.queue.backwards_entries) == 1 or not player.current:
            player.queue.internal.appendleft(player.queue.backwards.popleft())
            return await player.stop()

        player.queue.internal.appendleft(player.queue.backwards.popleft())
        player.queue.internal.appendleft(player.queue.backwards.popleft())

        player.update = True

        await player.stop()

    @commands.command(name='stop')
    @commands.cooldown(3, 30, commands.BucketType.guild)
    async def stop_(self, ctx):
        """Stop the player, disconnect and clear the queue.
        Examples
        ----------
        <prefix>stop
            {ctx.prefix}stop
        """
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        if not player.is_connected:
            return await ctx.send('I am not currently connected to voice!')

        if await self.has_perms(ctx, manage_guild=True):
            await ctx.send(f'{ctx.author.mention} has stopped the player as an admin or DJ.', delete_after=25)
            return await self.do_stop(ctx)

        await self.do_vote(ctx, player, 'stop')

    async def do_stop(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        await player.destroy_controller()
        await player.stop()
        await player.disconnect()

    @commands.command(name='volume', aliases=['vol'])
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
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        if not player.is_connected:
            return await ctx.send('I am not currently connected to voice!')

        if not 0 < value < 101:
            return await ctx.send('Please enter a value between 1 and 100.')

        if not await self.has_perms(ctx, manage_guild=True) and player.dj.id != ctx.author.id:
            if (len(player.connected_channel.members) - 1) > 2:
                return

        await player.set_volume(value)
        await ctx.send(f'Set the volume to **{value}**%', delete_after=7)

        if not player.updating and not player.update:
            await player.invoke_controller()

    @commands.command(name='queue', aliases=['q', 'que'])
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
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        if not player.is_connected:
            return await ctx.send('I am not currently connected to voice!')

        entries = [f'{i} - [{e.title}]({e.uri})' if not e.is_dead else f'**{i} -** ~~{e.title}~~'
                   for i, e in enumerate(player.queue.entries, 1)]

        if not entries:
            return await ctx.send('```\nNo more songs in the Queue!\n```', delete_after=15)

        await ctx.paginate(title=f'Upcoming({len(entries)} entries) Page', entries=entries)

    @commands.command(name='remove_songs', aliases=['removesongs', 'rs'])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def remove_songs_(self, ctx, *tracks):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        if not player.is_connected:
            return await ctx.send('I am not currently connected to voice!')

        if not await self.has_perms(ctx, manage_guild=True):
            return await ctx.send('Only the DJ or an Admins may remove songs from the queue!')

        success = []

        for track in tracks:
            try:
                item = player.queue.entries[int(track) - 1]
                item.dead = True
            except IndexError:
                pass
            else:
                success.append(item.title)

        if not success:
            return await ctx.send('No songs were removed. Check you are removing valid tracks.')

        await ctx.paginate(title=f'Successfully removed ({len(success)}) songs... Page ', entries=success)

    @commands.command(name='clear', aliases=['wipe'])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def clear_(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        if not player.is_connected:
            return await ctx.send('I am not currently connected to voice!')

        if not await self.has_perms(ctx, manage_guild=True):
            return await ctx.send('Only the DJ or an Admins may clear the queue!')

        for track in player.queue.entries:
            track.dead = True

        await ctx.send(f'Succesfully cleared the Queue. ({len(player.queue.entries)} tracks)')

        player.update = True

    @commands.command(name='shuffle', aliases=['mix'])
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
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        if not player.is_connected:
            return await ctx.send('I am not currently connected to voice!')

        if len(player.queue.entries) < 3:
            return await ctx.send('Please add more songs to the queue before trying to shuffle.', delete_after=10)

        if await self.has_perms(ctx, manage_guild=True):
            await ctx.send(f'{ctx.author.mention} has shuffled the playlist as an admin or DJ.', delete_after=25)
            return await self.do_shuffle(ctx)

        await self.do_vote(ctx, player, 'shuffle')

    async def do_shuffle(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)
        random.shuffle(player.queue.internal)

        player.update = True

    @commands.command(name='repeat', aliases=['replay'])
    async def repeat_(self, ctx):
        """Repeat the currently playing song.
        Examples
        ----------
        <prefix>repeat
            {ctx.prefix}repeat
        """
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        if not player.is_connected:
            return

        if await self.has_perms(ctx, manage_guild=True):
            await ctx.send(f'{ctx.author.mention} has repeated the song as an admin or DJ.', delete_after=25)
            return await self.do_repeat(ctx)

        await self.do_vote(ctx, player, 'repeat')

    async def do_repeat(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        if not player.queue.entries:
            player.queue.put(player.current)
        else:
            player.queue.put_left(player.current)

        player.update = True

    @commands.command(name='vol_up', hidden=True)
    async def volume_up(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        if not player.is_connected:
            return

        vol = int(math.ceil((player.volume + 10) / 10)) * 10

        if vol > 100:
            vol = 100
            await ctx.send('Maximum volume reached', delete_after=7)

        await player.set_volume(vol)

        player.update = True

    @commands.command(name='vol_down', hidden=True)
    async def volume_down(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        if not player.is_connected:
            return

        vol = int(math.ceil((player.volume - 10) / 10)) * 10

        if vol < 0:
            vol = 0
            await ctx.send('Player is currently muted', delete_after=10)

        await player.set_volume(vol)

        player.update = True

    @commands.command()
    async def set_eq(self, ctx, *, mode: str):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        await player.set_preq(mode)
        await ctx.send(f'Player has been set to {mode}.')

    @commands.command()
    async def set_eq2(self, ctx, *args):
        if len(args) != 14:
            await ctx.send('EQ must be 14 Bands long.')

        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        levels = [(i, float(v)) for i, v in enumerate(args)]

        await player.set_eq(levels=levels)
        await ctx.send(f'Set EQ to: `{levels}`')

    @commands.command(utils.EvieeCommand)
    async def info(self, ctx):
        """Retrieve various Node/Server/Player information."""
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)
        node = player.node

        used = humanize.naturalsize(node.stats.memory_used)
        total = humanize.naturalsize(node.stats.memory_allocated)
        free = humanize.naturalsize(node.stats.memory_free)
        cpu = node.stats.cpu_cores

        fmt = f'**WaveLink:** `{wavelink.__version__}`\n\n' \
              f'Connected to `{len(self.bot.wavelink.nodes)}` nodes.\n' \
              f'Best available Node `{self.bot.wavelink.get_best_node().__repr__()}`\n' \
              f'`{len(self.bot.wavelink.players)}` players are distributed on nodes.\n' \
              f'`{node.stats.players}` players are distributed on server.\n' \
              f'`{node.stats.playing_players}` players are playing on server.\n\n' \
              f'Server Memory: `{used}/{total}` | `({free} free)`\n' \
              f'Server CPU: `{cpu}`\n\n' \
              f'Server Uptime: `{datetime.timedelta(milliseconds=node.stats.uptime)}`'
        await ctx.send(fmt)


def setup(bot):
    bot.add_cog(Music(bot))
