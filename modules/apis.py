import discord
from discord.ext import commands

import asyncio
import importlib
import inspect
import itertools
import os
import random
import re
import subprocess
import textwrap

import utils


class DPYSource:
    def __init__(self, **attrs):
        self.file = attrs.get('file')
        self.obj = attrs.get('obj')
        self.parent = attrs.get('parent')
        self.index = attrs.get('index')
        self.path = attrs.get('path')
        self.match = attrs.get('match')


class Colour(metaclass=utils.MetaCog, category='API', colour=random.randint(0, 16581375),
             thumbnail='https://i.imgur.com/g2LpJZb.png'):
    """Somewhere over the rainbow... An Eviee awaits!
    These commands should help you feel all nice inside."""

    __slots__ = ('bot', 'BASE', 'BASE_S', '_invalid', '_pattern')

    def __init__(self, bot):
        self.bot = bot

        self.BASE = 'http://www.thecolorapi.com/id?format=json&hex={}'
        self.BASE_S = 'http://www.colourlovers.com/api/palettes?hex={}&format=json'

        _invalid = ('#', '0x', 'rgb', '(', ')', ',', ' ')
        self._invalid = dict((re.escape(_), '' if _ not in (',', ' ') else ' ') for _ in _invalid)
        self._pattern = re.compile("|".join(self._invalid.keys()))

    def get_hex(self, value):
        value = self._pattern.sub(lambda m: self._invalid[re.escape(m.group(0))], value)

        try:
            value = '%02x%02x%02x' % tuple(map(int, value.split()))
        except (ValueError, TypeError):
            pass

        return value

    @commands.command(name='colour', aliases=['color'], cls=utils.AbstractorGroup, abstractors=['show'])
    async def _colour(self, ctx, *, value: str):
        """Retrieve information on a colour and get a scheme, from an RGB or HEX value.

        [!This command is also a Base Command!]

        Aliases
        --------
            color

        Parameters
        ------------
        value: [rgb, HEX]
            The colour value to retrieve data for. This can be formatted in multiple ways.

        Examples
        ----------
        <prefix>colour <value>
        <prefix>show colour <value>

            {ctx.prefix}colour rgb(255, 255, 255)
            {ctx.prefix}show colour #FFFFFF
            {ctx.prefix}colour rgb 255,255,255
            {ctx.prefix}colour 255 255 255
        """
        await ctx.trigger_typing()

        orig = value
        value = self.get_hex(value.lower())

        efmt = f'I could not find any colour matching value: **`{orig}`**\n' \
               f'```css\n[Your colour is either invalid or not supported. Please try again. ' \
               f'Supported Formats: RGB or HEX]\n```'

        try:
            resp, data = await self.bot.aio('get', self.BASE.format(value), return_attr='json')
        except Exception as e:
            return await ctx.send(f'There was an error processing your request.\n```css\n[{e}]\n```')

        if resp.status != 200:
            return await ctx.send(efmt)

        try:
            _hex = data['hex']['clean']
        except KeyError:
            return await ctx.send(efmt)
        if _hex.lower() != value:
            return await ctx.send(efmt)

        resp_s, data_s = await self.bot.aio('get', self.BASE_S.format(value), return_attr='json')

        try:
            image = data_s[0]['imageUrl']
            colours = data_s[0]['colors']
        except (IndexError, KeyError):
            image = f'https://dummyimage.com/300/{data["hex"]["clean"]}.png'
            colours = None

        try:
            emcol = int(f"0x{_hex}", 0)
        except ValueError:
            return await ctx.send(efmt)

        embed = discord.Embed(title=f'Colour - {data["name"]["value"]}', colour=emcol)
        embed.set_thumbnail(url=f'https://dummyimage.com/150/{data["hex"]["clean"]}.png')
        embed.set_image(url=image)
        embed.add_field(name='HEX', value=f'{data["hex"]["value"]}')
        embed.add_field(name='RGB', value=f'{data["rgb"]["value"]}')
        embed.add_field(name='HSL', value=f'{data["hsl"]["value"]}')
        embed.add_field(name='HSV', value=f'{data["hsv"]["value"]}')
        embed.add_field(name='CMYK', value=f'{data["cmyk"]["value"]}')
        embed.add_field(name='XYZ', value=f'{data["XYZ"]["value"]}')
        if colours:
            embed.add_field(name='Scheme:', value=' | '.join(colours), inline=False)

        await ctx.send(embed=embed)

    @_colour.command(name='show')
    async def show_colour(self, ctx, *, value: str):
        """An aliases and base command to colour."""
        await ctx.invoke(self.bot.get_command('colour'), value=value)


class Source(metaclass=utils.MetaCog, category='API', thumbnail='https://i.imgur.com/DF5ZfSh.png'):
    """Commands which allow you to Get that Juicy Sauce Code from various locations."""

    __slots__ = ('bot', 'rtfs_anchors', 'rtfs_revision')

    def __init__(self, bot):
        self.bot = bot
        self.rtfs_anchors = None
        self.rtfs_revision = None

        bot.loop.create_task(self._update_rtfs())

    async def get_rtfs_revision(self):
        cmd = r'git ls-remote https://github.com/Rapptz/discord.py --tags rewrite HEAD~1..HEAD --format="%s (%cr)"'
        if os.name == 'posix':
            cmd = cmd.format(r'\`%h\`')
        else:
            cmd = cmd.format(r'`%h`')
        revision = os.popen(cmd).read().strip()

        return revision.split()[0]

    def rtfs_embed(self, search, matches):
        if not matches:
            embed = discord.Embed(title=f'RTFS - <{search}>',
                                  description=f'Sorry no results were found for {search}\n\nTry being more specific.',
                                  colour=0x6dc9c9)
            embed.add_field(name='Discord.py Source:', value='https://github.com/Rapptz/discord.py/tree/rewrite/')
        else:
            matches = '\n'.join(matches)
            embed = discord.Embed(title=f'RTFS - <{search}>', description=f'{matches}', colour=0x6dc9c9)

        return embed

    async def _update_rtfs(self):
        while not self.bot.is_closed():
            try:
                revision = await self.get_rtfs_revision()
            except Exception:
                await asyncio.sleep(600)
                continue

            if not self.rtfs_revision:
                pass
            elif self.rtfs_revision == revision:
                await asyncio.sleep(3600)
                continue

            if os.name == 'nt':
                await self._rtfs_load()
                return

            try:
                cmd = 'python3.6 -m pip install -U git+https://github.com/Rapptz/discord.py.git@rewrite'
                process = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)

                output, error = process.communicate()
                process.kill()
            except Exception:
                pass

            await self._rtfs_load()

    async def _rtfs_load(self):
        self.rtfs_revision = await self.get_rtfs_revision()

        anchors = []
        parent = None

        pf = r'def (.*?[a-zA-Z0-9])\(.*\)'
        pc = r'class (.*[a-zA-Z0-9])[\:\(]'

        def pred(y):
            if inspect.isbuiltin(y):
                return

            try:
                return 'discord' in y.__name__
            except AttributeError:
                return False

        importlib.reload(discord)

        mods = inspect.getmembers(discord, pred) + inspect.getmembers(commands, pred)
        for x in mods:
            file = x[1].__name__.split('.')[-1]
            path = '/'.join(x[1].__name__.split('.')[:-1])

            try:
                src = inspect.getsourcelines(x[1])
            except TypeError:
                continue

            for index, line in enumerate(src[0]):
                orig = line

                if sum(1 for _ in itertools.takewhile(str.isspace, line)) > 4:
                    continue
                elif line == 0 or '__' in line:
                    continue

                line = line.lstrip(' ')
                match = re.match(pf, line)

                if match:
                    if sum(1 for _ in itertools.takewhile(str.isspace, orig)) < 4:
                        parent = None

                elif not match:
                    match = re.match(pc, line)
                    if match:
                        parent = match.group(1)

                try:
                    obj = match.group(1)
                except AttributeError:
                    continue

                attrs = {'file': file, 'obj': obj, 'parent': parent if parent != obj else None, 'index': index,
                         'path': path,
                         'match': f'{file}.{parent if parent and parent != obj else ""}'
                                  f'{"." if parent and parent != obj else ""}{obj}'}

                anchor = DPYSource(**attrs)
                anchors.append(anchor)

        self.rtfs_anchors = anchors

    @commands.command(name='rtfs', aliases=['dsauce', 'dsource', 'dpysauce', 'dpysource'], cls=utils.EvieeCommand)
    async def _rtfs(self, ctx, *, source: str=None):
        """Retrieve source code for discord.py.

        Parameters
        ------------
        source: [Optional]
            The file, function, class, method or path to retrieve source for. Could be none to display
            the base URL.

        Examples
        ----------
        <prefix>rtfs <source>

            {ctx.prefix}rtfs bot.py
            {ctx.prefix}rtfs Guild.members
            {ctx.prefix}rtfs Guild
            {ctx.prefix}rtfs member
        """
        orig = source
        surl = 'https://github.com/Rapptz/discord.py/blob/rewrite/'
        to_return = []

        if source is None:
            return await ctx.send('https://github.com/Rapptz/discord.py/tree/rewrite/')

        if source.endswith('.py'):
            source = source.replace('.py', '').lower()

            matches = utils.fuzzyfinder(source, [(a, a.file) for a in self.rtfs_anchors],
                                        key=lambda t: t[1], lazy=False)[:5]

            for f in matches:
                to_return.append(f'[{f[0].file}.py]({surl}{f[0].path}/{f[0].file}.py)')

        elif '.' in source:
            matches = utils.fuzzyfinder(source, [(a, a.match) for a in self.rtfs_anchors], key=lambda t: t[1],
                                        lazy=False)[:5]

            if not matches:
                matches = utils.fuzzyfinder(source, [(a, a.match.split('.', 1)[-1]) for a in self.rtfs_anchors],
                                            key=lambda t: t[1], lazy=False)[:5]

            for a in matches:
                a = a[0]
                to_return.append(f'[{a.match}]({surl}{a.path}/{a.file}.py#L{a.index + 1})')
        else:
            matches = utils.fuzzyfinder(source, [(a, a.obj) for a in self.rtfs_anchors], key=lambda t: t[1],
                                        lazy=False)[:5]

            for a in matches:
                a = a[0]
                to_return.append(f'[{a.match}]({surl}{a.path}/{a.file}.py#L{a.index + 1})')

        to_return = set(to_return)
        await ctx.send(embed=self.rtfs_embed(orig, sorted(to_return, key=lambda a: len(a))))

    @commands.command(name='source', aliases=['sauce'], cls=utils.EvieeCommand)
    async def get_source(self, ctx, *, target: str=None):
        """Retrieve the source code of a bot command or cog.

        Aliases
        ---------
            sauce

        Parameters
        ------------
        target: [Optional]
            The command or cog to retrieve source for. Could be none to display the base URL.

        Examples
        ----------
        <prefix>source <target>
        <prefix>sauce <target>

            {ctx.prefix}source prefix
            {ctx.prefix}source Fun
        """
        if not target:
            return await ctx.send('<https://github.com/EvieePy/EvieeBot>')

        cmd = self.bot.get_command(target)
        cog = self.bot.get_cog(target)
        ext = self.bot.get_ext(target)

        if cmd:
            code = textwrap.dedent(inspect.getsource(cmd.callback))
        elif cog:
            code = textwrap.dedent(inspect.getsource(cog.__class__))
        elif ext:
            code = textwrap.dedent(inspect.getsource(ext))
        else:
            embed = discord.Embed(title=f'Source - <{target.strip()}>',
                                  description=f'Sorry no results were found for {target.strip()}\n\n'
                                              f'Make sure you specify a valid command or cog.',
                                  colour=0x6dc9c9)
            embed.add_field(name='EvieeBot', value='https://github.com/EvieePy/EvieeBot')
            return await ctx.send(embed=embed)

        bin_ = await self.bot.create_bin(data=code)
        embed = discord.Embed(title=f'Source - <{target}>', description=f'{bin_}.py', colour=0x6dc9c9)

        return await ctx.send(embed=embed)
