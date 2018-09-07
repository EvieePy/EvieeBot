import discord
from discord.ext import commands

import asyncio
import datetime
import functools
import json
import os
import random
import time
import youtube_dl
from osuapi import OsuApi, AHConnector

import utils

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

ytdl = youtube_dl.YoutubeDL(ytdlopts)


class Misc(metaclass=utils.MetaCog, category='Misc', colour=0xa5d8d8, thumbnail='https://i.imgur.com/WGjcdqg.png'):
    """Miscellaneous commands which don't really have a place in this life... What am I even doing with mine!?
     I need a tequila.
     """

    __slots__ = ('bot', 'omdb', 'osu', 'vcontrols', 'scores', 'questions')

    def __init__(self, bot):
        self.bot = bot
        self.omdb = bot._config.get('OMDB', '_token')
        self.osu = OsuApi(bot._config.get('OSU', '_token'), connector=AHConnector())

        with open('./resources/MBTIS.json') as f:
            self.scores = json.load(f)

        with open('./resources/MBTI.json') as f:
            self.questions = json.load(f)

        bot.loop.create_task(self.temp_checker())

    async def __error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f'You are only permitted to one Channel per 15m.\n```css\n'
                           f'Your cooldown expires in: [{int(error.retry_after / 60)} minutes.]\n```')

        elif isinstance(error, commands.BotMissingPermissions):
            missing = ', '.join(error.missing_perms)
            await ctx.send(f'I am missing permissions to run this command: ```css\n[{missing}]\n```')

    async def __local_check(self, ctx):
        if ctx.invoked_with == 'help':
            return True
        elif ctx.invoked_with == 'invite':
            return True
        elif ctx.invoked_with == 'feedback':
            return True

        if not ctx.guild:
            await ctx.send('You are not able to use this command in Private Messages.')
            return False
        return True

    async def on_voice_state_update(self, mem, before, after):
        if not after.channel:
            return

        async with self.bot.pool.acquire() as conn:
            chan = await conn.fetchval("""SELECT autoroom FROM guilds WHERE guilds.id IN ($1)""", mem.guild.id)

        if after.channel.id == chan:
            async with self.bot.pool.acquire() as conn:
                old = await conn.fetchval("""SELECT cid FROM tempchannels WHERE mid IN ($1)""", mem.id)
            if old:
                chan = self.bot.get_channel(old)
                try:
                    return await mem.move_to(chan)
                except Exception:
                    pass

            chan = await self.generate_channel(mem.guild, mem, name=str(mem))
            await mem.move_to(chan)

    @property
    def fb_chan(self):
        return self.bot.get_channel(352013640691351552)

    @property
    def hellos(self):
        return 'Hello', 'Hi', 'Hey', 'Heya', 'Heyo', 'Hai', 'Howdy!', "G'Day!", 'Hey there', 'Hai there', 'Hola'

    @commands.command(name='emojis', aliases=['emotes'], cls=utils.EvieeCommandGroup)
    async def emojis_(self, ctx, *, name: str=None):
        """Display all emojis I can see in a paginated embed.

        Aliases
        ---------
            emotes

        Sub-Commands
        --------------
            guild

        Examples
        ----------
        <prefix>emojis
        <prefix>emojis guild

            {ctx.prefix}emojis
            {ctx.prefix}emojis guild
        """
        if name:
            emojis = [e for e in self.bot.emojis if name in e.name]
            if not emojis:
                return await ctx.send(f'Could not find any emojis with search term: `{name}`')

            chunks = [e async for e in utils.pager(sorted(emojis, key=lambda _: _.name), 8)]
        else:
            chunks = [e async for e in utils.pager(sorted(self.bot.emojis, key=lambda _: _.name), 8)]

        pagey = utils.EmojiPaginator(title='Emojis', chunks=chunks)
        self.bot.loop.create_task(pagey.paginate(ctx))

    @emojis_.command(name='guild', aliases=['server'])
    async def guild_emojis(self, ctx, *, guild: utils.GuildConverter=None):
        if not guild:
            guild = ctx.guild

        chunks = [e async for e in utils.pager(sorted(list(guild.emojis), key=lambda _: _.name), 8)]

        if not chunks:
            return await ctx.send('This guild has no custom emojis.')

        pagey = utils.EmojiPaginator(title=f'Emojis | {ctx.guild.name}', chunks=chunks)
        self.bot.loop.create_task(pagey.paginate(ctx))

    @commands.command(name='emoji', cls=utils.EvieeCommand)
    async def emoji(self, ctx, *, emoji: discord.Emoji):
        """Retrieve information about an emoji I can see."""
        embed = discord.Embed(title=emoji.name, colour=0xEEEE00)
        embed.add_field(name='Guild', value=f'`{emoji.guild.name} (ID: {emoji.guild.id})`')
        embed.add_field(name='URL', value=f'[Open]({emoji.url})')
        embed.set_thumbnail(url=emoji.url)

        await ctx.paginate(extras=[embed], )

    @commands.command(name='hi', clas=utils.EvieeCommand)
    async def hello(self, ctx):
        """Say hello to Eviee."""
        await ctx.send(f'{random.choice(self.hellos)} {ctx.author.display_name}! <:3cc:431696022461349888>')

    @commands.command(name='autoroom', cls=utils.AbstractorGroup, abstractors=['add', 'remove'])
    @commands.bot_has_permissions(move_members=True)
    @utils.bot_has_permissions_guild(manage_channels=True)
    async def auto_room(self, ctx):
        """Creates a Channel which creates Temp Channels when entered.

        Examples
        ----------
        <prefix>autoroom add
        <prefix>autoroom remove

            {ctx.prefix}autoroom add
            {ctx.prefix}add autoroom
            {ctx.prefix}remove autoroom
        """
        await ctx.invoke(self.add_auto_room)

    @auto_room.command(name='add')
    @commands.bot_has_permissions(move_members=True)
    @utils.bot_has_permissions_guild(manage_channels=True)
    async def add_auto_room(self, ctx):
        """Creates an Auto Temp Room creator."""
        try:
            cat = discord.utils.get(ctx.guild.categories, name='TEMP CHANNELS')
            if not cat:
                cat = await ctx.guild.create_category(name='TEMP CHANNELS')

            async with self.bot.pool.acquire() as conn:
                chan = await conn.fetchval("""SELECT autoroom FROM guilds WHERE id IN ($1)""", ctx.guild.id)
                chan = self.bot.get_channel(chan)

            if chan:
                return await ctx.send('Your guild already has an Auto Temp Room.')

            chan = await ctx.guild.create_voice_channel(name='🎧 Auto Temp 🎧', overwrites={
                ctx.guild.default_role: discord.PermissionOverwrite(mute_members=False,
                                                                    deafen_members=False,
                                                                    connect=True,
                                                                    speak=False,
                                                                    move_members=False,
                                                                    manage_channels=False,
                                                                    manage_roles=False),
                ctx.guild.me: discord.PermissionOverwrite(move_members=True)},
                                                        category=cat,
                                                        reason='Auto Temp Channels.')
        except discord.HTTPException:
            return await ctx.send('Something went wrong while trying to create your channel. Please try again.')

        async with self.bot.pool.acquire() as conn:
            await conn.execute("""UPDATE guilds SET autoroom = $1 WHERE guilds.id IN ($2)""", chan.id, ctx.guild.id)

        await ctx.send('Your Auto Room has been setup!')

    @auto_room.command(name='remove')
    @commands.bot_has_permissions(manage_channels=True, move_members=True)
    async def remove_auto_room(self, ctx):
        """N/A"""
        pass

    @commands.command(name='temp', aliases=['temp_channel'], cls=utils.EvieeCommand)
    @commands.cooldown(1, 900, commands.BucketType.user)
    @utils.bot_has_permissions_guild(manage_channels=True)
    async def temp_chan(self, ctx, *, name: str=None):
        """Create a temporary Voice Channel.

        The Channel creator has the ability to remove, mute members etc.
        The Channel expires when the room becomes empty.

        Aliases
        ---------
            temp_channel
            temp_chan

        Parameters
        ------------
        name: str [Optional]
            The name for your channel. This defaults to your username#discriminator combo.

        Examples
        ----------
        <prefix>temp <name>

            {ctx.prefix}temp Cool Channel
        """
        if not name:
            name = f"{ctx.author}'s-room"

        try:
            chan = await self.generate_channel(ctx.guild, ctx.author, name=name)
        except discord.HTTPException:
            return await ctx.send('Something went wrong while trying to create your channel. Please try again.')

        await ctx.send(f'**{ctx.author.mention}Your channel has been created.**\nOther members may now join **`{chan}`**\n'
                       f'```ini\nYour channel will be destroyed shortly after the channel becomes empty.\n'
                       f'You may change permissions, channel name and more while the channel is active.\n'
                       f'By Default, `@everyone` are able to speak.```',
                       delete_after=30)

    async def generate_channel(self, guild, mem, name=None):
        cat = discord.utils.get(guild.categories, name='TEMP CHANNELS')
        if not cat:
            cat = await guild.create_category(name='TEMP CHANNELS')

        chan = await guild.create_voice_channel(name=name,
                                                overwrites={
                                                        mem: discord.PermissionOverwrite(mute_members=True,
                                                                                         deafen_members=True,
                                                                                         connect=True,
                                                                                         speak=True,
                                                                                         move_members=True,
                                                                                         manage_channels=True,
                                                                                         manage_roles=True,),
                                                        guild.default_role: discord.PermissionOverwrite(
                                                            speak=True,
                                                            connect=True
                                                        )},
                                                category=cat,
                                                reason='Temp Channel.')

        async with self.bot.pool.acquire() as conn:
            query = """INSERT INTO tempchannels(cid, gid, mid, ts) VALUES($1, $2, $3, $4)"""
            await conn.execute(query, chan.id, guild.id, mem.id, datetime.datetime.utcnow())

        return chan

    @utils.backoff_loop()
    async def temp_checker(self):
        await asyncio.sleep(120)

        async with self.bot.pool.acquire() as conn:
            temps = await conn.fetch("""SELECT * FROM tempchannels""")
            query = """DELETE FROM tempchannels WHERE cid IN ($1)"""

            for c in temps:
                ts = c['ts']
                ts = datetime.datetime.utcnow() - ts

                if ts.total_seconds() < 60:
                    continue

                chan = self.bot.get_channel(c['cid'])

                if not chan:
                    await conn.execute(query, c['cid'])
                elif len(chan.members) == 0:
                    await conn.execute(query, chan.id)

                    try:
                        await chan.delete(reason='Temp Channel: Empty for too long.')
                    except discord.HTTPException:
                        pass

    @commands.command(name='feedback', aliases=['fb', 'suggest'], cls=utils.EvieeCommand)
    @commands.cooldown(1, 180, commands.BucketType.user)
    async def feedback_(self, ctx, *, feedback: str=None):
        """Leave feedback regarding Eviee.

        Aliases
        ---------
            fb
            suggest

        Parameters
        ------------
        feedback: str [Required]
            A message to leave as feedback.

        Examples
        ----------
        <prefix>feedback <feedback>

            {ctx.prefix}feedback <3 Eviee
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
        if ctx.guild:
            embed.add_field(name='Guild', value=f'{ctx.guild.name}({ctx.guild.id})')
        else:
            embed.add_field(name='Private Message', value='True')

        embed.add_field(name='User', value=f'{ctx.author}({ctx.author.id})')
        embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar_url)
        embed.set_footer(text='Received ').timestamp = datetime.datetime.utcnow()
        embed.set_thumbnail(url=ctx.author.avatar_url)

        await ctx.send('Thanks your report has been submitted! You can report again in 3 minutes.', delete_after=45)
        await msg.delete()
        await self.fb_chan.send(embed=embed)

    @commands.command(name='invite')
    async def get_invite(self, ctx):
        """Invite Eviee to your guild!"""
        embed = discord.Embed(colour=0xff69b4, title='Invite Eviee')
        embed.add_field(name='With Permissions', value=
                        '[Click Me!](https://discordapp.com/oauth2/authorize?client_id=319047630048985099&scope=bot'
                        '&permissions=70642774)')
        embed.add_field(name='Without Permissions', value=
                        '[Click Me!](https://discordapp.com/oauth2/authorize?client_id=319047630048985099&scope=bot'
                        '&permissions=0)')

        await ctx.send(embed=embed)

    @commands.command(name='tinyurl', cls=utils.EvieeCommand)
    async def generate_tinyurl(self, ctx, *, link: str):
        """Generate a tinyurl from a link."""
        resp, cont = await self.bot.aio(method='get', url=f'http://tinyurl.com/api-create.php?url={link}',
                                        return_attr='text')
        await ctx.send(f'<{cont}>')

    @commands.command(name='getsong', aliases=['song_download', 'downloadsong'], cls=utils.EvieeCommand)
    async def download_ytaudio(self, ctx, *, search: str):
        """Downloads a song from YouTube and sends it back to the user.

        Parameters
        ------------
        search: [Required]
            The song you would like to download. This could be URL, Youtube ID or simple search.

        Examples
        ----------
        <prefix>getsong <search>

            {ctx.prefix}getsong Never gonna give you up.
        """
        # todo Filter non YouTube stuff.
        # todo Better error handling on large files.

        msg = await ctx.send('Attempting to retrieve your song.')

        try:
            await self.retrieve_song(ctx, search)
        except Exception as e:
            await ctx.send(f'There was an error retrieving your song:\n```css\n[{e}]\n```')

        try:
            await msg.delete()
        except discord.HTTPException:
            pass

    async def retrieve_song(self, ctx, search):
        async with ctx.typing():
            to_do = functools.partial(ytdl.extract_info, url=search, download=True)
            data = await utils.evieecutor(to_do, loop=self.bot.loop)

            if 'entries' in data:
                data = data['entries'][0]

            f = ytdl.prepare_filename(data)

            try:
                await ctx.send(content=None, file=discord.File(f, filename=f'{data["title"]}.{data["ext"]}'))
            except discord.HTTPException as e:
                await ctx.send(f'There was an error processing your song.\n```css\n[{e}]\n```')

            os.remove(f)

    @commands.command(name='quote', cls=utils.EvieeCommand)
    async def get_quote(self, ctx, *, mid: int):
        """Retrieve a message from your guild and quote it.

        Parameters
        ------------
        mid: [Required]
            The message ID to quote. This must be a valid message ID.
            You can retrieve IDs by turning developer mode on and right clicking on the message.

        Examples
        ----------
        <prefix>quote <mid>

            {ctx.prefix}quote 439045167790686208
        """
        async with self.bot.pool.acquire() as conn:
            msg = await conn.fetch("""SELECT * FROM messages WHERE mid IN($1)""", mid)

        if not msg:
            return await ctx.send('I could not find this message.')

        msg = msg[0]

        user = self.bot.get_user(msg['aid'])
        guild = self.bot.get_guild(msg['gid'])

        content = self.bot.fkey.decrypt(msg['content'].encode()).decode()
        embed = discord.Embed(title=str(user) if user else 'Unknown User', description=content, colour=0x36393E)

        if user:
            embed.set_thumbnail(url=user.avatar_url)

        attachment = msg['attachment']
        if attachment:
            embed.set_image(url=attachment)

        embed.set_footer(text=f'Sent in {guild} - #{guild.get_channel(msg["cid"])}').timestamp = msg['ts']

        await ctx.send(embed=embed)

    @commands.command(name='movie', aliases=['omdb'], cls=utils.EvieeCommand)
    async def get_movie(self, ctx, *, search: str):
        # TODO Fix

        resp, cont = await self.bot.aio(url=f'http://www.omdbapi.com/?apikey={self.omdb}&t={search}&r=json',
                                        return_attr='json', method='get')

        if cont['Response'] == 'False':
            return await ctx.send(f'I could not find a movie matching: `{search}`')

        embed = discord.Embed(title=cont['Title'], description=cont['Plot'], colour=0xF3CE13)
        embed.set_thumbnail(url='https://i.imgur.com/gbuXLtz.png')
        embed.set_image(url=cont['Poster'])

        embed.add_field(name='Released', value=cont['Released'])
        embed.add_field(name='Rating', value=cont['Rated'])
        embed.add_field(name='Director', value=cont['Director'])
        embed.add_field(name='Runtime', value=cont['Runtime'])

        stars = '\n'.join(cont['Actors'].split(', '))
        embed.add_field(name='Starring', value=stars)

        embed.add_field(name='Critics', value=f'Metascore - **`{cont["Metascore"]}`**\n'
                                              f'IMDb          - **`{cont["imdbRating"]}`**')

        await ctx.send(embed=embed)

    @commands.command(name='decrypt', invoke_without_command=True, cls=utils.EvieeCommandGroup)
    async def decrypters(self, ctx):
        """Decryption commands."""
        pass

    @decrypters.command(name='binary', aliases=['b1nary', '0101', '01'])
    async def decrpyt_binary(self, ctx, *, inp: str):
        """Decrypt binary

        Parameters
        ------------
        input: [Required]
            The binary input to decrypt.

        Examples
        ----------
        <prefix>decrypt binary <input>

            {ctx.prefix}decrypt binary 01000101 01110110 01101001 01100101 01100101
        """
        inp = inp.replace(' ', '')

        try:
            out = ''.join(chr(int(inp[i * 8:i * 8 + 8], 2)) for i in range(len(inp) // 8))
        except Exception:
            return await ctx.send('**This is not binary!**')

        return await ctx.send(out)

    @commands.command(name='osu', cls=utils.EvieeCommand)
    async def osu_(self, ctx, *, user: utils.OsuConverter=None):
        if not user:
            user = ctx.author

        if isinstance(user, discord.Member):
            async with self.bot.pool.acquire() as conn:
                osu = await conn.fetchval("""SELECT username FROM osu WHERE id IN($1)""", user.id)
                if not osu:
                    return await ctx.send(f'{user} does not have an osu! account linked.\n'
                                          f'`Set one with: {ctx.prefix}setosu osu_username`')
        else:
            osu = user

        results = await self.osu.get_user(osu)
        if not results:
            return await ctx.send(f'Could not find an osu! account matching: `{osu}`')

        results = results[0]

        embed = discord.Embed(title=f'{results.username} | {results.country}',
                              description=f'#{results.pp_rank} ({results.pp_raw} pp)', colour=0x8866ee)
        if isinstance(user, discord.Member):
            embed.set_thumbnail(url=user.avatar_url)
        else:
            embed.set_thumbnail(url='http://a.ppy.sh/%s?_=%s' % (results.user_id, time.time()))

        embed.add_field(name='Level', value=results.level)
        embed.add_field(name='Plays', value=results.playcount)
        embed.add_field(name='Accuracy', value=f'{results.accuracy:0.2f}%')
        embed.add_field(name='Hits', value=results.total_hits)
        embed.set_image(url=f'http://lemmmy.pw/osusig/sig.php?'
                            f'colour=hex8866ee&'
                            f'uname={results.username}&'
                            f'pp=1&'
                            f'flagshadow&'
                            f'onlineindicator=undefined&'
                            f'xpbar')

        await ctx.send(embed=embed)

    @commands.command(name='setosu', cls=utils.EvieeCommand)
    async def set_osu(self, ctx, *, name: str):
        async with self.bot.pool.acquire() as conn:
            await conn.execute("""INSERT INTO osu(id, username) VALUES($1, $2)
                                  ON CONFLICT(id) DO UPDATE SET username = $2 WHERE osu.id IN($1)""",
                               ctx.author.id, name)

        await ctx.send(f'Successfully set your osu! account to: `{name}`')

    @commands.command(name='vote', aliases=['yn'], cls=utils.EvieeCommand)
    async def vote_(self, ctx):
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

        opener = await ctx.send('What would you like to initiate a vote for?')
        try:
            resp = await self.bot.wait_for('message', check=lambda x: x.author.id == ctx.author.id, timeout=300)
        except asyncio.TimeoutError:
            return await ctx.send('You took too long to respond. Please try again!')

        desc = resp.content

        try:
            await resp.delete()
        except discord.HTTPException:
            pass

        await opener.delete()
        msg = await ctx.send(f"**Ok, your question is:** {desc}.\n\n"
                             f"How long should the vote last? (Enter in seconds from 0(Until closed) to 1800(30 minutes).")

        resp = await self.bot.wait_for('message', check=lambda x: x.author.id == ctx.author.id, timeout=300)
        await msg.delete()

        try:
            resp = int(resp.content)
        except ValueError:
            return await ctx.send('Invalid time provided. Please try running the command again.')

        embed = discord.Embed(title=f'{desc}?', colour=0xffb347, description='To vote simply use the reactions!')
        embed.set_author(name=str(ctx.author), icon_url=ctx.author.avatar_url)

        poll = await ctx.send(embed=embed)
        Vote(ctx, poll, resp, desc)

    @commands.command(name='mbti', cls=utils.EvieeCommand)
    async def mbti_test(self, ctx):
        """Take the MBTI Personality Test"""
        embeds = []

        for q in self.questions.values():

            try:
                q['C']
            except KeyError:
                embed = discord.Embed(title=q['Q'], description=f'A - {q["A"]}\n\nB - {q["B"]}',
                                      colour=0xA25576)
            else:
                embed = discord.Embed(title=q['Q'], description=f'A - {q["A"]}\n\nB - {q["B"]}\n\nC - {q["C"]}',
                                      colour=0xA25576)

            embed.set_thumbnail(url='https://i.imgur.com/1juScvA.png')
            embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar_url)
            embed.set_footer(text='MBTI Personality Test')
            embeds.append(embed)

        MBTI(ctx, embeds, self.scores)


class MBTI:

    def __init__(self, ctx, pages, scores):
        self.ctx = ctx
        self.bot = ctx.bot
        self.controls = {'🇦': 'A', '🇧': 'B', '🇨': 'C'}
        self.pages = pages
        self.scores = scores
        self.base = None

        self.results = {'E': 0, 'I': 0,
                        'S': 0, 'N': 0,
                        'T': 0, 'F': 0,
                        'J': 0, 'P': 0}
        self.result = []

        self.bot.loop.create_task(self.reaction_loop())

    async def reaction_loop(self):
        self.base = await self.ctx.send(embed=self.pages[0])
        count = 0

        for reaction in self.controls:
            try:
                await self.base.add_reaction(str(reaction))
            except discord.HTTPException:
                return

        def check(r, u):
            if not self.base:
                return False
            elif str(r) not in self.controls.keys():
                return False
            elif u.id != self.ctx.author.id:
                return False
            return True

        while not self.bot.is_closed():
            count += 1

            try:
                react, user = await self.bot.wait_for('reaction_add', check=check, timeout=180)
            except asyncio.TimeoutError:
                await self.base.delete()
                return

            try:
                await self.base.remove_reaction(react, user)
            except discord.HTTPException:
                pass

            answer = self.controls.get(str(react))

            if answer == 'C':
                try:
                    self.scores[str(count)][answer]
                except KeyError:
                    count -= 1
                    continue

            result = self.scores[str(count)][answer]

            self.results[result[0]] += result[1]

            try:
                self.pages[count]
            except IndexError:
                break
            else:
                await self.base.edit(embed=self.pages[count])

        if self.results['I'] >= self.results['E']:
            self.result.append('I')
        else:
            self.result.append('E')

        if self.results['N'] >= self.results['S']:
            self.result.append('N')
        else:
            self.result.append('S')

        if self.results['T'] >= self.results['F']:
            self.result.append('T')
        else:
            self.result.append('F')

        if self.results['P'] >= self.results['J']:
            self.result.append('P')
        else:
            self.result.append('J')

        result = ''.join(self.result)
        embed = discord.Embed(title='MBTI Personality Test Results:', description=f'\n**{result}**')
        embed.add_field(name='Read More:', value=f'[Click Me!](https://www.16personalities.com/{result}-personality)')
        embed.set_author(name=self.ctx.author.display_name, icon_url=self.ctx.author.avatar_url)
        embed.set_thumbnail(url=self.ctx.author.avatar_url)
        await self.base.delete()
        await self.ctx.send(embed=embed)


class Vote:

    def __init__(self, ctx, poll, wait, desc):
        self.ctx = ctx
        self.bot = ctx.bot
        self.poll = poll
        self.wait = wait
        self.desc = desc
        self.event = asyncio.Event()

        self.vcontrols = ('⬆', '⬇', '❎')

        self.do_task = self.bot.loop.create_task(self.do_vote())

    async def do_vote(self):
        for reaction in self.vcontrols:
            try:
                await self.poll.add_reaction(str(reaction))
            except discord.HTTPException:
                return

        voted = set()
        self.ups = 0
        self.downs = 0

        self.killer = self.bot.loop.create_task(self.kill_vote())

        while not self.bot.is_closed():
            def check(r, u):
                if str(r) not in self.vcontrols:
                    return False
                elif u.id == self.bot.user.id or r.message.id != self.poll.id:
                    return False
                elif u.id in voted and str(r) != '❎':
                    return False
                return True

            try:
                react, user = await self.bot.wait_for('reaction_add', check=check, timeout=3600)
            except asyncio.TimeoutError:
                break

            voted.add(user.id)

            if str(react) == '⬆':
                self.ups += 1
            elif str(react) == '⬇':
                self.downs += 1
            elif str(react) == '❎':
                if user.id != self.ctx.author.id:
                    continue
                await self.poll.delete()
                break
            else:
                continue

            try:
                await self.poll.remove_reaction(react, user)
            except discord.HTTPException:
                pass

        try:
            self.killer.cancel()
        except Exception:
            pass

        embed = discord.Embed(title='Vote Results:', description=self.desc, colour=0xffb347)
        embed.add_field(name='Up Votes', value=str(self.ups))
        embed.add_field(name='Down Votes', value=str(self.downs))
        await self.ctx.send(embed=embed)

    async def kill_vote(self):
        if self.wait == 0:
            return

        await asyncio.sleep(self.wait)
        await self.poll.delete()
        
        try:
            self.do_task.cancel()
        except Exception:
            pass

        embed = discord.Embed(title='Vote Results:', description=self.desc, colour=0xffb347)
        embed.add_field(name='Up Votes', value=str(self.ups))
        embed.add_field(name='Down Votes', value=str(self.downs))
        await self.ctx.send(embed=embed)


class Observations(metaclass=utils.MetaCog, thumbnail='https://i.imgur.com/oA6lvQq.png'):
    """Commands which help you understand this cruel world and its surrounds better.
    Maybe..."""

    __slots__ = ('bot', )

    def __init__(self, bot):
        self.bot = bot

    @property
    def weather_key(self):
        return self.bot._config.get('WEATHER', '_token')

    @property
    def nasa_key(self):
        return self.bot._config.get('NASA', '_token')

    @commands.command(name='weather', cls=utils.EvieeCommand)
    async def get_weather(self, ctx, *, location: str=None):
        """Retrieve weather information for a location.

        Parameters
        ------------
        location: [Required]
            The location to retrieve weather information for.

        Examples
        ----------
        <prefix>weather <location>

            {ctx.prefix}weather Sydney
        """
        if not location:
            return await ctx.send('Please provide a valid location.')

        try:
            resp, cont = await self.bot.aio('get', url=f'http://api.apixu.com/v1/current.json?'
                                                       f'key={self.weather_key}&'
                                                       f'q={location}', return_attr='json')
        except Exception as e:
            self.bot.dispatch('command_error', ctx, e)
            return await ctx.send(f'There was an error retrieving weather information:\n```css\n{e}\n```')

        loc = cont['location']
        current = cont['current']
        condition = current['condition']

        if current['is_day'] == 1:
            colour = 0xFDB813
        else:
            colour = 0x546bab

        embed = discord.Embed(title=f'Weather for {loc["name"]}, {loc["region"]} {loc["country"]}',
                              description=f'{condition["text"]}', colour=colour)
        embed.set_thumbnail(url=f'http:{condition["icon"]}')

        embed.add_field(name='Temp', value=f'{current["temp_c"]}℃ | {current["temp_f"]}℉')
        embed.add_field(name='Feels Like', value=f'{current["feelslike_c"]}℃ | {current["feelslike_f"]}℉')
        embed.add_field(name='Humidity', value=f'{current["humidity"]}%')
        embed.add_field(name='Cloud Coverage', value=f'{current["cloud"]}%')
        embed.add_field(name='Wind Speed', value=f'{current["wind_kph"]}kph | {current["wind_mph"]}mph')
        embed.add_field(name='Wind Direction', value=f'{current["wind_dir"]} - {current["wind_degree"]}°')
        embed.add_field(name='Precipitation', value=f'{current["precip_mm"]}mm | {current["precip_in"]}in')
        embed.add_field(name='Visibility', value=f'{current["vis_km"]}km | {current["vis_miles"]}miles')
        embed.set_footer(text=f'Local Time: {loc["localtime"]}')

        await ctx.send(embed=embed)

    @commands.command(name='apod', aliases=['iotd'], cls=utils.EvieeCommand)
    async def nasa_apod(self, ctx):
        """Returns NASA's Astronomy Picture of the day.

        Examples
        ----------
        <prefix>apod

            {ctx.prefix}apod
        """
        url = f'https://api.nasa.gov/planetary/apod?api_key={self.nasa_key}'

        try:
            resp, cont = await self.bot.aio(method='get', url=url, return_attr='json')
        except Exception as e:
            return await ctx.send(f'There was an error processing APOD.\n```css\n[{e}]\n```')

        embed = discord.Embed(title='Astronomy Picture of the Day', description=f'**{cont["title"]}** | {cont["date"]}'
                                                                                f'\n{cont["explanation"]}')

        img = cont["url"]
        if not img.endswith(('gif', 'png', 'jpg')):
            embed.add_field(name='Watch', value=f"[Click Me](http:{cont['url']})")
        else:
            embed.set_image(url=cont['url'])

        try:
            embed.add_field(name='HD Download', value=f'[Click here!]({cont["hdurl"]})')
        except KeyError:
            pass

        embed.timestamp = datetime.datetime.utcnow()
        embed.set_footer(text='Generated ')

        await ctx.send(embed=embed)

    @commands.command(name='epic', aliases=['EPIC'], cls=utils.EvieeCommand)
    async def nasa_epic(self, ctx):
        """Returns NASA's most recent EPIC image.

        Examples
        ---------
        <prefix>epic

            {ctx.prefix}epic
        """
        # todo Add the ability to select a date.
        base = f'https://api.nasa.gov/EPIC/api/natural?api_key={self.nasa_key}'
        img_base = 'https://epic.gsfc.nasa.gov/archive/natural/{}/png/{}.png'

        try:
            rep, cont = await self.bot.aio(method='get', url=base, return_attr='json')
        except Exception as e:
            return await ctx.send(f'There was an error processing your EPIC request.\n```css\n[{e}]\n```')

        img = random.choice(cont)
        coords = img['centroid_coordinates']

        embed = discord.Embed(title='NASA EPIC', description=f'{img["caption"]}', colour=0x1d2951)
        embed.set_image(url=img_base.format(img['date'].split(' ')[0].replace('-', '/'), img['image']))
        embed.add_field(name='Centroid Coordinates',
                        value=f'Lat: {coords["lat"]} | Lon: {coords["lon"]}')
        embed.add_field(name='Download',
                        value=f"[Click Me]({img_base.format(img['date'].split(' ')[0].replace('-', '/'), img['image'])})")

        embed.timestamp = datetime.datetime.utcnow()
        embed.set_footer(text='Generated on ')

        await ctx.send(embed=embed)

