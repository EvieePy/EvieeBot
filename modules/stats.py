import discord
from discord.ext import commands

import asyncio
import datetime
import functools
import humanize
import inspect
import itertools
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import psutil
import numpy as np
import os
import pathlib
from io import BytesIO
from matplotlib.ticker import MultipleLocator
from more_itertools import ilen, with_iter
from PIL import Image, ImageSequence, ImageFont, ImageDraw, ImageColor

import utils


def format_delta(*, delta, brief=False):
    hours, remainder = divmod(int(delta.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    days, hours = divmod(hours, 24)

    if not brief:
        if days:
            fmt = '{d} d, {h} h, {m} m, and {s} s'
        else:
            fmt = '{h} h, {m} m, and {s} s'
    else:
        fmt = '{h}:{m}:{s}'
        if days:
            fmt = '{d}days, ' + fmt

    return fmt.format(d=days, h=hours, m=minutes, s=seconds)


class Stats(metaclass=utils.MetaCog, colour=0xffebba, thumbnail='https://i.imgur.com/Y8Q8siB.png'):
    """Want to know some boring stuff about the bot, yourself and others?
    These are your commands... In depth information is only an Eviee away!"""

    __slots__ = ('bot', 'statuses')

    def __init__(self, bot):
        self.bot = bot
        self.statuses = {'online': '<:dot_online:420205881200738314>', 'offline': '<:dot_invis:420205881272172544>',
                         'dnd': '<:dot_dnd:420205879883726858>', 'idle': '<:dot_idle:420205880508809218>'}

        self.bot.loop.create_task(self.expiry_check())

    async def get_perms(self, ctx, target: utils.Union(discord.Member, discord.Role), *, previous=None):

        cembed = discord.Embed(title=f'Channel Permissions for {target.name}',
                               description=f'Channel: **`{ctx.channel.name}`**\n',
                               colour=target.colour)
        gembed = discord.Embed(title=f'Guild Permissions for {target.name}', colour=target.colour)

        voice_perms = [p for (p, v) in discord.Permissions().voice() if v]
        extras = [cembed]

        if not isinstance(target, discord.Role):
            perms_for = ctx.channel.permissions_for
            cperms = {'t': '\n'.join(p for (p, v) in perms_for(target) if v),
                      'f': '\n'.join(p for (p, v) in perms_for(target) if not v and p not in voice_perms)}
            gperms = {'t': '\n'.join(p for (p, v) in tuple(target.guild_permissions) if v),
                      'f': '\n'.join(p for (p, v) in tuple(target.guild_permissions) if not v)}
            gembed.add_field(name='Allowed', value=gperms['t'])
            gembed.add_field(name='Denied', value=gperms['f'] or 'None')
            gembed.set_footer(text='<< Channel Permissions')
            extras.append(gembed)
        else:
            cperms = {'t': '\n'.join(p for (p, v) in tuple(target.permissions) if v),
                      'f': '\n'.join(p for (p, v) in tuple(target.permissions) if not v and p not in voice_perms)}

        cembed.add_field(name='Allowed', value=cperms['t'])
        cembed.add_field(name='Denied', value=cperms['f'] or 'None')

        if len(extras) > 1 and previous:
            cembed.set_footer(text=f'<< {previous} | Guild Permissions >>')

        return extras

    def build_game(self, member, embed=None):
        activity = member.activity

        try:
            if activity.small_image_url:
                embed.set_author(name=member.display_name, icon_url=activity.small_image_url)
            embed.set_image(url=activity.large_image_url)

            if activity.party:
                party = f'({activity.party["size"][0]} of {activity.party["size"][1]})'
            else:
                party = ""

            embed.description = f'{activity.details}\n{activity.state} {party}'
        except AttributeError:
            pass

        embed.title = f'Playing - {activity.name}'
        embed._colour = discord.Colour(0x7289da)

        if activity.start:
            pf = datetime.datetime.utcnow() - activity.start
            embed.add_field(name='Playing For:', value=format_delta(delta=pf, brief=True))
        return embed

    def build_spotify(self, member, embed=None):
        activity = member.activity

        if not embed:
            embed = utils.EvieeBed()
            embed.set_thumbnail(url=member.avatar_url)
            embed.set_footer(icon_url='https://i.imgur.com/o434xfQ.png',
                             text=f'Listening with Spotify... {member}')

        embed.set_image(url=activity.album_cover_url)
        embed.title = f'{activity.title}'
        embed._colour = activity.color

        artists = ', '.join(activity.artists)
        embed.description = f'by **`{artists}`**.'
        embed.extra = f'{activity.title} {artists}'

        embed.add_field(name='Album', value=activity.album)
        embed.add_field(name='Duration', value=format_delta(delta=activity.duration, brief=True))
        embed.add_field(name='Open in Spotify',
                        value=f'[Play now!](https://open.spotify.com/track/{activity.track_id})')

        return embed

    async def build_activity(self, member, embed=None):
        activity = member.activity

        if activity.type == discord.ActivityType.unknown:
            return None

        if not embed:
            embed = utils.EvieeBed()
            embed.set_thumbnail(url=member.avatar_url)
            embed.set_footer(text='<< Member Info | Channel Permissions >>')

        if isinstance(activity, discord.Spotify):
            embed = self.build_spotify(member, embed)
        elif activity.type == discord.ActivityType.playing:
            embed = self.build_game(member, embed)

        return embed

    @commands.command(name='profile', cls=utils.EvieeCommand, aliases=['userinfo'])
    async def _profile(self, ctx, *, member: discord.Member=None):
        """Show profile information for a member. Includes activity, permissions and other info.

        Parameters
        ------------
        member
            The member to get information from. This can be in the form of an ID, Name, or Mention.

        Examples
        ----------
        <prefix>profile
        <prefix>profile Eviee

            {ctx.prefix}profile
            {ctx.prefix}profile Eviee
        """
        if member is None:
            member = ctx.author

        aembed = None

        activity = member.activity
        embed = utils.EvieeBed(title=f'Profile for {member}',
                               colour=member.colour,
                               description=f'```ini\n'
                                           f'ID      : {member.id}\n'
                                           f'CREATED : [{member.created_at.strftime("%d %b, %Y @ %H:%M")}]\n'
                                           f'JOINED  : [{member.joined_at.strftime("%d %b, %Y @ %H:%M")}]\n'
                                           f'```')
        embed.set_thumbnail(url=member.avatar_url)
        embed.add_field(name='Display Name', value=member.display_name)
        embed.add_field(name='Status', value=f'{self.statuses.get(str(member.status))} **`{member.status}`**')
        embed.add_field(name='Top Role', value=member.top_role.mention)
        embed.add_field(name='Profile', value=member.mention)

        if activity:
            embed.set_footer(text='Current Activity Info >>')
            embed.add_field(name='Activity', value=f'**`{activity.type.name.capitalize()}` | **{activity.name}')
            aembed = await self.build_activity(member)
            previous = 'Current Activity Info'
        else:
            embed.set_footer(text='Channel Permissions >>')
            previous = 'Member Info'

        perms = await self.get_perms(ctx, member, previous=previous)
        pagey = utils.ProfilePaginator(extras=[embed, aembed, *perms], member=member, timeout=120)
        self.bot.loop.create_task(pagey.paginate(ctx))

    @commands.command(name='spotify', aliases=['listening'], cls=utils.EvieeCommandGroup)
    async def get_spotify(self, ctx, *, member: discord.Member=None):
        """Show currently playing information from Spotify for a user, yourself or your guild.

        Parameters
        ------------
        member
            The member to get information from. This can be in the form of an ID, Name, or Mention.

        Aliases
        ---------
            listening

        Sub-Commands
        --------------
            guild: [Display Spotify information about your guild.]

        Examples
        ----------
        <prefix>spotify
        <prefix>spotify Eviee
        <prefix>spotify guild

            {ctx.prefix}spotify
            {ctx.prefix}spotify Eviee
            {ctx.prefix}spotify guild
        """
        if not member:
            member = ctx.author

        if not isinstance(member.activity, discord.Spotify):
            return await ctx.send(f'**`{member}`** is not listening to Spotify with Discord integration!')

        return await ctx.send(embed=self.build_spotify(member))

    @get_spotify.command(name='guild')
    async def guild_spotify(self, ctx, *, guild: int=None):
        """Show currently playing information from Spotify for your guild.

        Parameters
        ------------
        guild: Optional
            This argument is not required. And defaults to your guild. An ID can be passed.

        Examples
        ----------
        <prefix>spotify guild
        <prefix>spotify guild <guild_id>

            {ctx.prefix}spotify guild
            {ctx.prefix}spotify guild 352006920560967691
        """
        if not guild:
            guild = ctx.guild
        else:
            guild = self.bot.get_guild(guild)

        if not guild:
            return await ctx.send('Could not find a guild with that ID.')

        members = [m for m in guild.members if isinstance(m.activity, discord.Spotify)]

        if not members:
            return await ctx.send('No one in your guild is listening to Spotify with Discord.')

        pages = []
        for member in members:
            embed = utils.EvieeBed()
            embed.set_author(name=member.display_name, icon_url=member.avatar_url)
            embed.set_thumbnail(url=member.avatar_url)
            embed.set_footer(icon_url='https://i.imgur.com/o434xfQ.png',
                             text=f'Listening with Spotify... {member}')
            pages.append(self.build_spotify(member, embed=embed))

        pagey = utils.SpotifyPaginator(extras=pages)
        self.bot.loop.create_task(pagey.paginate(ctx))

    @commands.command(name='activity')
    async def get_activity(self, ctx, *, member: discord.Member=None):
        """Show currently activity information for a guild member.

        Parameters
        ------------
        member
            The member to get information from. This can be in the form of an ID, Name, or Mention.

        Examples
        ----------
        <prefix>activity
        <prefix>activity Eviee


            {ctx.prefix}activity
            {ctx.prefix}activity Eviee
        """
        if not member:
            member = ctx.author

        if not member.activity:
            return await ctx.send(f'**`{member}`** is not currently doing anything.')

        embed = discord.Embed(colour=0x7289da)
        embed.set_thumbnail(url=member.avatar_url)

        return await ctx.paginate(extras=[await self.build_activity(member, embed)])

    @commands.command(name='avatar', aliases=['pfp', 'ava'], cls=utils.EvieeCommand)
    async def get_avatar(self, ctx, *, member: discord.Member=None):
        if not member:
            member = ctx.author

        return await ctx.send(member.avatar_url)

    @commands.command(name='perms', aliases=['permissions'], cls=utils.EvieeCommand)
    async def show_perms(self, ctx, *, target: utils.Union(discord.Member, discord.Role)=None):
        """Display permissions for a user or role."""
        if not target:
            target = ctx.author

        pages = await self.get_perms(ctx, target=target)
        await ctx.paginate(extras=pages)

    def pager(self, entries, chunk: int):
        for x in range(0, len(entries), chunk):
            yield entries[x:x + chunk]

    def hilo(self, numbers, indexm: int=1):
        highest = [index * indexm for index, val in enumerate(numbers) if val == max(numbers)]
        lowest = [index * indexm for index, val in enumerate(numbers) if val == min(numbers)]

        return highest, lowest

    def datetime_range(self, start, end, delta):
        current = start
        while current < end:
            yield current
            current += delta

    def get_times(self):
        # todo this is really bad so fix soon pls thanks kk weeeew

        fmt = '%H%M'
        current = datetime.datetime.utcnow()
        times = []
        times2 = []
        times3 = []
        tcount = 0

        rcurrent = current - datetime.timedelta(minutes=60)
        rcurrent2 = current - datetime.timedelta(minutes=30)
        for x in range(7):
            times.append(rcurrent + datetime.timedelta(minutes=tcount))
            tcount += 10

        tcount = 0
        for x in range(7):
            times2.append(rcurrent2 + datetime.timedelta(minutes=tcount))
            tcount += 5

        tcount = 0
        for t3 in range(26):
            times3.append(rcurrent + datetime.timedelta(minutes=tcount))
            tcount += 60/25

        times = [t.strftime(fmt) for t in times]
        times2 = [t.strftime(fmt) for t in times2]
        times3 = [t.strftime(fmt) for t in times3]

        return times, times2, times3, current

    def ping_plotter(self, *, name, data: (tuple, list)=None):

        # Base Data
        if data is None:
            numbers = list(self.bot._wspings)
        else:
            numbers = list(data)

        long_num = list(itertools.chain.from_iterable(itertools.repeat(num, 2) for num in numbers))
        chunks = tuple(self.pager(numbers, 4))

        avg = list(itertools.chain.from_iterable(itertools.repeat(np.average(x), 8) for x in chunks))
        mean = [np.mean(numbers)] * 60
        prange = int(max(numbers)) - int(min(numbers))
        plog = np.log(numbers)

        t = np.sin(np.array(numbers) * np.pi*2 / 180.)
        xnp = np.linspace(-np.pi, np.pi, 60)
        # tmean = [np.mean(t)] * 60

        # Spacing/Figure/Subs
        plt.style.use('ggplot')
        fig = plt.figure(figsize=(15, 7.5))
        ax = fig.add_subplot(2, 2, 2, facecolor='aliceblue', alpha=0.3)   # Right
        ax2 = fig.add_subplot(2, 2, 1, facecolor='thistle', alpha=0.2)  # Left
        ax3 = fig.add_subplot(2, 1, 2, facecolor='aliceblue', alpha=0.3)  # Bottom
        ml = MultipleLocator(5)
        ml2 = MultipleLocator(1)

        # Times
        times, times2, times3, current = self.get_times()

        # Axis's/Labels
        plt.title(f'Latency over Time ({name}) | {current} UTC')
        ax.set_xlabel(' ')
        ax.set_ylabel('Network Stability')
        ax2.set_xlabel(' ')
        ax2.set_ylabel('Milliseconds(ms)')
        ax3.set_xlabel('Time(HHMM) UTC')
        ax3.set_ylabel('Latency(ms)')

        if min(numbers) > 100:
            ax3.set_yticks(np.arange(min(int(min(numbers)), 2000) - 100,
                                     max(range(0, int(max(numbers)) + 100)) + 50, max(numbers) / 12))
        else:
            ax3.set_yticks(np.arange(min(0, 1), max(range(0, int(max(numbers)) + 100)) + 50, max(numbers) / 12))

        # Labels
        ax.yaxis.set_minor_locator(ml2)
        ax2.xaxis.set_minor_locator(ml2)
        ax3.yaxis.set_minor_locator(ml)
        ax3.xaxis.set_major_locator(ml)

        ax.set_ylim([-1, 1])
        ax.set_xlim([0, np.pi])
        ax.yaxis.set_ticks_position('right')
        ax.set_xticklabels(times2)
        ax.set_xticks(np.linspace(0, np.pi, 7))
        ax2.set_ylim([min(numbers) - prange/4, max(numbers) + prange/4])
        ax2.set_xlim([0, 60])
        ax2.set_xticklabels(times)
        ax3.set_xlim([0, 120])
        ax3.set_xticklabels(times3, rotation=45)
        plt.minorticks_on()
        ax3.tick_params()

        highest, lowest = self.hilo(numbers, 2)

        mup = []
        mdw = []
        count = 0
        p10 = mean[0] * (1 + 0.5)
        m10 = mean[0] * (1 - 0.5)

        for x in numbers:
            if x > p10:
                mup.append(count)
            elif x < m10:
                mdw.append(count)
            count += 1

        # Axis 2 - Left
        ax2.plot(range(0, 60), list(itertools.repeat(p10, 60)), '--', c='indianred',
                 linewidth=1.0,
                 markevery=highest,
                 label='+10%')
        ax2.plot(range(0, 60), list(itertools.repeat(m10, 60)), '--', c='indianred',
                 linewidth=1.0,
                 markevery=highest,
                 label='+-10%')
        ax2.plot(range(0, 60), numbers, '-', c='blue',
                 linewidth=1.0,
                 label='Mark Up',
                 alpha=.8,
                 drawstyle='steps-post')
        ax2.plot(range(0, 60), numbers, ' ', c='red',
                 linewidth=1.0,
                 markevery=mup,
                 label='Mark Up',
                 marker='^')
        """ax2.plot(range(0, 60), numbers, ' ', c='green',
                 linewidth=1.0, markevery=mdw,
                 label='Mark Down',
                 marker='v')"""
        ax2.plot(range(0, 60), mean, label='Mean', c='blue',
                linestyle='--',
                linewidth=.75)
        ax2.plot(list(range(0, 60)), plog, 'darkorchid',
                 alpha=.9,
                 linewidth=1,
                 drawstyle='default',
                 label='Ping')

        # Axis 3 - Bottom
        ax3.plot(list(range(0, 120)), long_num, 'darkorchid',
                 alpha=.9,
                 linewidth=1.25,
                 drawstyle='default',
                 label='Ping')
        ax3.fill_between(list(range(0, 120)), long_num, 0, facecolors='darkorchid', alpha=0.3)
        ax3.plot(range(0, 120), long_num, ' ', c='indianred',
                 linewidth=1.0,
                 markevery=highest,
                 marker='^',
                 markersize=12)
        ax3.text(highest[0], max(long_num) - 10, f'{round(max(numbers))}ms', fontsize=12)
        ax3.plot(range(0, 120), long_num, ' ', c='lime',
                 linewidth=1.0,
                 markevery=lowest,
                 marker='v',
                 markersize=12)
        ax3.text(lowest[0], min(long_num) - 10, f'{round(min(numbers))}ms', fontsize=12)
        ax3.plot(list(range(0, 120)), long_num, 'darkorchid',
                 alpha=.5,
                 linewidth=.75,
                 drawstyle='steps-pre',
                 label='Steps')
        ax3.plot(range(0, 120), avg, c='forestgreen',
                 linewidth=1.25,
                 markevery=.5,
                 label='Average')

        # Axis - Right
        """ax.plot(list(range(0, 60)), plog1, 'darkorchid',
                 alpha=.9,
                 linewidth=1,
                 drawstyle='default',
                 label='Ping')
        ax.plot(list(range(0, 60)), plog2, 'darkorchid',
                 alpha=.9,
                 linewidth=1,
                 drawstyle='default',
                 label='Ping')
        ax.plot(list(range(0, 60)), plog10, 'darkorchid',
                 alpha=.9,
                 linewidth=1,
                 drawstyle='default',
                 label='Ping')"""

        ax.fill_between(list(range(0, 120)), .25, 1, facecolors='lime', alpha=0.2)
        ax.fill_between(list(range(0, 120)), .25, -.25, facecolors='dodgerblue', alpha=0.2)
        ax.fill_between(list(range(0, 120)), -.25, -1, facecolors='crimson', alpha=0.2)
        ax.fill_between(xnp, t, 1, facecolors='darkred')

        """ax.plot(list(range(0, 60)), t, 'darkred',
                linewidth=1.0,
                alpha=1,
                label='Stability')
        ax.plot(list(range(0, 60)), tmean, 'purple',
                linewidth=1.0,
                alpha=1,
                linestyle=' ')
        ax.plot(list(range(0, 60)), tp10, 'limegreen',
                linewidth=1.0,
                alpha=1,
                linestyle=' ')
        ax.plot(list(range(0, 60)), tm10, 'limegreen',
                linewidth=1.0,
                alpha=1,
                linestyle=' ')"""

        # Legend
        ax.legend(bbox_to_anchor=(.905, .97), bbox_transform=plt.gcf().transFigure)
        ax3.legend(loc='best', bbox_transform=plt.gcf().transFigure)

        # Grid
        ax.grid(which='minor')
        ax2.grid(which='both')
        ax3.grid(which='both')
        plt.grid(True, alpha=0.25)

        # Inverts
        ax.invert_yaxis()

        f = BytesIO()
        plt.savefig(f, bbox_inches='tight')
        f.seek(0)

        plt.clf()
        plt.close()
        return f

    @commands.command(name='wsping', cls=utils.EvieeCommand)
    @commands.cooldown(1, 45, commands.BucketType.user)
    async def ws_ping(self, ctx):
        """WebSocket Pings, shown as a pretty graph."""
        if len(self.bot._wspings) < 60:
            return await ctx.send(f'WS Latency: **`{self.bot.latency * 1000}`ms**')

        await ctx.channel.trigger_typing()

        to_do = functools.partial(self.ping_plotter, name='Websocket')
        pfile = await utils.evieecutor(to_do, loop=self.bot.loop)

        await ctx.send(file=discord.File(pfile, 'wsping.png'))

    @commands.command(name='rttping', cls=utils.EvieeCommand)
    @commands.cooldown(1, 45, commands.BucketType.user)
    async def rtt_ping(self, ctx):
        """RTT Pings, shown as a pretty graph."""
        if len(self.bot._rtts) < 60:
            return await ctx.send(f'Latest RTT: **`{self.bot._rtts[-1]}`ms**')

        await ctx.channel.trigger_typing()

        to_do = functools.partial(self.ping_plotter, data=self.bot._rtts, name='RTT')
        pfile = await utils.evieecutor(to_do, loop=self.bot.loop)

        await ctx.send(content=f'```ini\nLatest RTT: [{self.bot._rtts[-1]}]ms\n```',
                       file=discord.File(pfile, 'rttping.png'))

    async def on_message(self, msg):
        async with self.bot.pool.acquire() as conn:
            await conn.execute("""INSERT INTO stats(item, value) VALUES('messages', 1)
                                  ON CONFLICT(item)
                                    DO UPDATE SET value = COALESCE(stats.value, 0)::int + 1
                                    WHERE stats.item IN('messages')""")

        if msg.author.bot or not msg.guild:
            return

        if msg.attachments:
            if msg.attachments[0].filename.endswith(('jpg', 'png', 'gif')):
                attachment = msg.attachments[0].url
            else:
                attachment = None
        else:
            attachment = None

        expiry = datetime.datetime.utcnow() + datetime.timedelta(days=14)
        content = self.bot.fkey.encrypt(msg.content.encode()).decode()

        async with self.bot.pool.acquire() as conn:
            await conn.execute("""INSERT INTO messages(mid, aid, cid, gid, ts, content, attachment, expiry)
                                  VALUES($1, $2, $3, $4, $5, $6, $7, $8)""",
                               msg.id, msg.author.id, msg.channel.id, msg.guild.id, msg.created_at, content,
                               attachment, expiry)

    async def on_command_completion(self, ctx):
        async with self.bot.pool.acquire() as conn:
            await conn.execute("""INSERT INTO stats(item, value) VALUES('commands', 1)
                                  ON CONFLICT(item)
                                    DO UPDATE SET value = COALESCE(stats.value, 0)::int + 1
                                    WHERE stats.item IN('commands')""")

    @utils.backoff_loop()
    async def expiry_check(self):
        async with self.bot.pool.acquire() as conn:
            await conn.execute("""DELETE FROM messages WHERE now() >= messages.expiry""")

        await asyncio.sleep(10300)

    @commands.command(name='linecount', cls=utils.EvieeCommand)
    async def lc(self, ctx, target=None):
        cmd = self.bot.get_command(target)
        cog = self.bot.get_cog(target)
        ext = self.bot.get_ext(target)

        if cmd:
            length = len(inspect.getsourcelines(cmd.callback)[0])
        elif cog:
            length = len(inspect.getsourcelines(cog.__class__)[0])
        elif ext:
            length = len(inspect.getsourcelines(ext)[0])
        else:
            length = sum(ilen(with_iter(p.open(encoding='utf-8'))) for p in pathlib.Path('.').rglob('*.py')
                         if not str(p.parent).startswith('venv'))
            return await ctx.send(f'**Total Lines:** `{length}`')

        await ctx.send(f'**{target} Lines:** `{length}`')

    @commands.command(name='about', cls=utils.EvieeCommand, aliases=['info'])
    async def about_(self, ctx):
        async with self.bot.pool.acquire() as conn:
            coms = await conn.fetchval("""SELECT value FROM stats WHERE item IN('commands')""")
            messages = await conn.fetchval("""SELECT value FROM stats WHERE item IN('messages')""")

        uptime = format_delta(delta=datetime.datetime.utcnow() - self.bot.starttime, brief=False)
        memory = self.bot.proc.memory_full_info().uss / 1024 ** 2
        cpu = self.bot.proc.cpu_percent() / psutil.cpu_count()
        ping = np.average(list(self.bot._wspings))

        embed = discord.Embed(colour=0xff6961,
                              description=f'**Useful Links:**\n'
                                          f'[Support Server](https://discord.gg/EVxmWHS)\n'
                                          f'[Github Page](https://github.com/EvieePy/EvieeBot)\n'
                                          f'[Mystbin](http://mystb.in)\n'
                                          f'[Vote for Eviee](https://discordbots.org/bot/319047630048985099/vote)\n'
                                          f'Created by Eviee#0666 with Python 3.6.5.\n\n'
                                          f'{humanize.intcomma(int(messages))} messages read'
                                          f' with {humanize.intcomma(int(coms))} commands invoked in'
                                          f' {len(self.bot.guilds)} servers.\n\n'
                                          f'Currently up for {uptime}\n\n'
                                          f'Memory Usage   :  {memory:.2f} MiB\n'
                                          f'CPU Usage          :  {cpu:.2f} %\n'
                                          f'Avg Ping              : {ping:.2f} ms')
        embed.set_thumbnail(url=self.bot.user.avatar_url)
        embed.set_footer(text=f'Use {ctx.prefix}feedback to report bugs or leave feedback. <3')

        cmd = r'git show -s HEAD~5..HEAD --format="[{}](https://github.com/EvieePy/EvieeBot/commit/%H) %s (%cr)"'
        if os.name == 'posix':
            cmd = cmd.format(r'\`%h\`')
        else:
            cmd = cmd.format(r'`%h`')

        try:
            revision = os.popen(cmd).read().strip()
        except OSError:
            revision = 'Could not fetch due to memory error. Sorry.'

        gembed = discord.Embed(title='Latest Revisions:', description=revision)
        await ctx.paginate(extras=[embed, gembed])

    def make_pie(self):

        labels = 'Online', 'Offline', 'DnD', 'Idle'
        fracs = [10, 35, 35, 20]
        explode = (0.05, 0.05, 0.05, 0.05)
        colours = ('#43B581', '#747F8D', '#F04747', '#FAA61A')

        plt.pie(fracs, explode=explode, autopct='%.0f%%', shadow=False, colors=colours)

        pie = BytesIO()
        plt.savefig(pie, transparent=True)
        pie.seek(0)
        plt.clf()
        plt.close()

        with Image.open('resources/pie_legend.png') as base:
            with Image.open(pie) as chart:
                base.paste(chart, box=(-100, -80), mask=chart)

            f = BytesIO()
            base.save(f, 'png')
            f.seek(0)

        return f

    @commands.command(name='ps', aliases=['piestatus'])
    @commands.is_owner()
    async def pie_status(self, ctx):
        to_do = functools.partial(self.make_pie)
        pfile = await utils.evieecutor(to_do, loop=self.bot.loop)

        await ctx.send(file=discord.File(pfile, 'pie_test.png'))

    @commands.command('ca', cls=utils.EvieeCommand, hidden=True)
    @commands.is_owner()
    async def change_avy(self, ctx, url: str):
        async with self.bot.session.get() as resp:
            data = await resp.read()

        await self.bot.user.edit(avatar=data)

