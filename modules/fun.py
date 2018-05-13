import discord
from discord.ext import commands

import enum
import io
import random
from PIL import Image, ImageSequence, ImageFont, ImageDraw, ImageColor

import utils


class Fun(metaclass=utils.MetaCog, category='Fun', thumbnail='https://i.imgur.com/w8OIp4P.png'):
    """Commands which make life just that little bit more worth living."""

    __slots__ = ('bot',)

    def __init__(self, bot):
        self.bot = bot

    @property
    def hug_colour(self):
        return ImageColor.getcolor('#e94573', 'L')

    @property
    def _licks(self):
        return {'lick1': self.make_lick, 'lick2': self.make_lick2}

    async def make_hug(self, a, b):
        font = ImageFont.truetype('resources/fonts/Playtime.ttf', 12)

        invalid = (6, 8, 9, 10, 11)
        values = {12: 45, 14: 10, 17: 5, 20: 5, 23: 5}

        frames = []

        def generate():
            hugbase = 45

            with Image.open('resources/hug.gif') as base:
                for index, frame in enumerate(ImageSequence.Iterator(base)):
                    draw = ImageDraw.Draw(frame)

                    if index in invalid:
                        pass
                    else:
                        hugbase += values.get(index, 15)

                    draw.text((hugbase, 115), f'{a.display_name}', font=font, fill=self.hug_colour)
                    draw.text((170, 250), f'{b.display_name}', font=font, fill=self.hug_colour)

                    frames.append(frame.copy())
                    del draw

        await utils.evieecutor(generate, None, loop=self.bot.loop)

        f = io.BytesIO()
        frames[0].save(f, 'gif', save_all=True, duration=0, loop=0, append_images=frames[1:])
        f.seek(0)

        return discord.File(f, f'{a.id}{b.id}_hug.gif')

    async def make_bn(self, user, msg: str):
        font = ImageFont.truetype('resources/fonts/Playtime.ttf', 16)

        msg = ' '.join(msg.split())
        w, h = font.getsize(msg)

        frames = []

        def generate():
            with Image.open('resources/bn.gif') as base:
                for index, frame in enumerate(ImageSequence.Iterator(base)):
                    if index >= 7:
                        draw = ImageDraw.Draw(frame)
                        draw.fontmode = '1'
                        draw.text(((500 - w) / 2, (285 - h) / 2), msg, font=font, align='center', fill=99)
                        del draw
                        
                    frames.append(frame.copy())

        await utils.evieecutor(generate, None, loop=self.bot.loop)

        last_frame = frames[-1]

        for x in range(25):
            frames.append(last_frame.copy())

        f = io.BytesIO()
        frames[0].save(f, 'gif', save_all=True, duration=0.1, loop=0, append_images=frames[1:])
        f.seek(0)

        return discord.File(f, f'{user.id}_bn.gif')

    async def make_lick2(self, a, b):
        font = ImageFont.truetype('resources/fonts/Playtime.ttf', 30)

        aw, ah = font.getsize(a.display_name)
        bw, bh = font.getsize(b.display_name)

        frames = []

        def generate():
            with Image.open('resources/lick2.gif') as base:
                for index, frame in enumerate(ImageSequence.Iterator(base)):
                    draw = ImageDraw.Draw(frame)
                    draw.text(((420 - bw) / 2, 400), b.display_name, font=font, fill=self.hug_colour)
                    draw.text(((730 - aw) / 2, 60), a.display_name, font=font, fill=99)

                    frames.append(frame.copy())
                    del draw

        await utils.evieecutor(generate, None, loop=self.bot.loop)

        f = io.BytesIO()
        frames[0].save(f, 'gif', save_all=True, duration=0.1, loop=0, append_images=frames[1:])
        f.seek(0)

        return discord.File(f, f'{a.id}{b.id}_licks2.gif')

    async def make_lick(self, a, b):
        font = ImageFont.truetype('resources/fonts/Playtime.ttf', 30)

        aw, ah = font.getsize(a.display_name)
        bw, bh = font.getsize(b.display_name)

        frames = []

        def generate():
            with Image.open('resources/lick.gif') as base:
                for index, frame in enumerate(ImageSequence.Iterator(base)):
                    draw = ImageDraw.Draw(frame)
                    draw.text(((500 - bw) / 2, 450), b.display_name, font=font, fill=self.hug_colour)

                    if index >= 60 or index <= 8:
                        pass
                    else:
                        draw.text(((450 - aw) / 2, 150), a.display_name, font=font, align='center', fill=99)
                        # draw.text(((500 - w) / 2, (285 - h) / 2), msg, font=font, align='center', fill=99)

                    frames.append(frame.copy())
                    del draw

        await utils.evieecutor(generate, None, loop=self.bot.loop)
        last_frame = frames[-1]

        for x in range(25):
            frames.append(last_frame.copy())

        f = io.BytesIO()
        frames[0].save(f, 'gif', save_all=True, duration=0.1, loop=0, append_images=frames[1:])
        f.seek(0)

        return discord.File(f, f'{a.id}{b.id}_lick.gif')

    async def make_hearts(self, a, b):
        font = ImageFont.truetype('resources/fonts/Playtime.ttf', 20)

        aw, ah = font.getsize(a.display_name)
        bw, bh = font.getsize(b.display_name)

        frames = []

        def generate():
            with Image.open('resources/heart.gif') as base:
                for index, frame in enumerate(ImageSequence.Iterator(base)):
                    draw = ImageDraw.Draw(frame)
                    draw.text(((270 - bw) / 2, 70), b.display_name, font=font, fill=self.hug_colour)
                    draw.text(((730 - aw) / 2, 70), a.display_name, font=font, fill=99)

                    frames.append(frame.copy())
                    del draw

        await utils.evieecutor(generate, None, loop=self.bot.loop)

        f = io.BytesIO()
        frames[0].save(f, 'gif', save_all=True, duration=0.1, loop=0, append_images=frames[1:])
        f.seek(0)

        return discord.File(f, f'{a.id}{b.id}_hearts.gif')

    async def make_kiss(self, a, b):
        font = ImageFont.truetype('resources/fonts/Playtime.ttf', 15)

        aw, ah = font.getsize(a.display_name)
        bw, bh = font.getsize(b.display_name)

        frames = []

        def generate():
            with Image.open('resources/kiss.gif') as base:
                for index, frame in enumerate(ImageSequence.Iterator(base)):
                    draw = ImageDraw.Draw(frame)
                    draw.text(((240 - aw) / 2, 50), a.display_name, font=font, fill=99)
                    draw.text(((425 - bw) / 2, 275), b.display_name, font=font, fill=99)

                    frames.append(frame.copy())
                    del draw

        await utils.evieecutor(generate, None, loop=self.bot.loop)

        f = io.BytesIO()
        frames[0].save(f, 'gif', save_all=True, duration=0.1, loop=0, append_images=frames[1:])
        f.seek(0)

        return discord.File(f, f'{a.id}{b.id}_kiss.gif')

    @commands.command(name='kiss', aliases=['x'], cls=utils.EvieeCommand)
    @commands.cooldown(4, 90, commands.BucketType.user)
    async def give_kiss(self, ctx, *, member: discord.Member=None):
        """Send someone some kisses.

        Parameters
        ------------
        member:
            The member to give kisses to. This can be in the form of an ID, Name, or Mention.

        Examples
        ----------
        <prefix>kiss <member>

            {ctx.prefix}kiss Myst
        """
        if member is None:
            return await ctx.send("You can't kiss the air... **`xD`**")

        await ctx.trigger_typing()
        await ctx.send(file=await self.make_kiss(ctx.author, member))

    @commands.command(name='heart', aliases=['<3'], cls=utils.EvieeCommand)
    @commands.cooldown(4, 90, commands.BucketType.user)
    async def give_hearts(self, ctx, *, member: discord.Member = None):
        """Send someone some hearts.

        Parameters
        ------------
        member:
            The member to give hearts to. This can be in the form of an ID, Name, or Mention.

        Examples
        ----------
        <prefix>heart <member>

            {ctx.prefix}heart Myst
        """
        if member is None:
            return await ctx.send("You can't heart the air... **`xD`**")

        await ctx.trigger_typing()
        await ctx.send(file=await self.make_hearts(ctx.author, member))

    @commands.command(name='hug', cls=utils.AbstractorGroup, abstractors=['give'])
    @commands.cooldown(3, 90, commands.BucketType.user)
    async def give_hug(self, ctx, *, member: discord.Member = None):
        """Give someone a cute hug.

        Parameters
        ------------
        member:
            The member to give a hug to. This can be in the form of an ID, Name, or Mention.

        Examples
        ----------
        <prefix>hug <member>

            {ctx.prefix}hug Eviee
        """
        if member is None:
            return await ctx.send("You can't hug the air... **`xD`**")

        await ctx.trigger_typing()
        await ctx.send(file=await self.make_hug(ctx.author, member))

    @give_hug.command(name='give')
    async def _give_hug(self, ctx, *, member: discord.Member = None):
        await ctx.invoke(ctx.command.parent, member=member)

    @commands.command(name='bn', aliases=['breaking_news', 'breaking'], cls=utils.EvieeCommand)
    @commands.cooldown(3, 90, commands.BucketType.user)
    async def breaking_news(self, ctx, *, msg: str):
        """Display your Breaking News in a cute GIF.

        Aliases
        ---------
            breaking_news
            breaking

        Parameters
        ------------
        message:
            The text you would like to display as breaking news. This can not be longer than 50 characters.

        Examples
        ----------
        <prefix>bn <message>
        <preifx>breaking_news <message>

            {ctx.prefix}bn Myst is cool!
            {ctx.prefix}breaking Myst is cool!
            {ctx.prefix}breaking_news Myst to rule world!
        """
        if len(msg) > 50:
            return await ctx.send('The length of your breaking news can not be longer than 50 characters long!')

        await ctx.trigger_typing()
        await ctx.send(file=await self.make_bn(ctx.author, msg))

    @commands.command(name='lick', aliases=['licky'], cls=utils.EvieeCommand)
    @commands.cooldown(3, 90, commands.BucketType.user)
    async def give_lick(self, ctx, *, member: discord.Member = None):
        """Lick someone you love... Or hate, and annoy them!

        Aliases
        ---------
            licky

        Parameters
        ------------
        member:
            The member lick. This can be in the form of an ID, Name, or Mention.

        Examples
        ----------
        <prefix>lick <member>
        <preifx>licky <member>

            {ctx.prefix}lick @Myst
            {ctx.prefix}lick 319047630048985099
        """
        if member is None:
            return await ctx.send("You can't lick yourself!")

        await ctx.trigger_typing()

        n = random.randint(1, 2)
        await ctx.send(file=await self._licks[f'lick{n}'](ctx.author, member))

    @commands.command(name='dab', cls=utils.EvieeCommand)
    async def do_dab(self, ctx):
        await ctx.send('No.')


class RPSLS(enum.Enum):
    ROCK = 1
    SPOCK = 2
    PAPER = 3
    LIZARD = 4
    SCISSORS = 5

    CUT = 53
    COVERED = 31
    CRUSHED = 14
    POISONED = 42
    SMASHED = 25
    DECAPITATED = 54
    ATE = 43
    DISPROVED = 32
    VAPORIZED = 21
    BLUNTED = 15


class Games(metaclass=utils.MetaCog, category='Fun', thumbnail='https://i.imgur.com/E0pWuGW.png'):
    """Who said games!? These commands should keep you entertained...
    If only for a little bit.
    """
    __slots__ = ('bot', )

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='rpsls', aliases=['spr', 'psr', 'rps'], cls=utils.EvieeCommand)
    async def rpsls(self, ctx, *, hand):
        """Play a game of RPSLS against Eviee.

        Aliases
        ---------
            rps
            psr
            spr

        Examples
        ----------
        <prefix>rpsls <choice>

            {ctx.prefix}rpsls rock
        """
        try:
            player = RPSLS[hand.upper()]
        except KeyError:
            return await ctx.send('Invalid Option. Please choose either Rock, Paper, Scissors, Lizard or Spock.')

        choice = RPSLS(random.randint(1, 5))
        calc = (player.value - choice.value) % 5

        if calc == 0:
            embed = discord.Embed(title='We Drew!',
                                  description=f'`We both drew {choice.name.lower()}! This is awkward.`',
                                  colour=0x4192D9)

        elif 1 <= calc <= 2:
            embed = discord.Embed(title='You Win!',
                                  description=f'`I chose {choice.name.lower()} and you'
                                              f' {RPSLS(int(f"{player.value}{choice.value}")).name.lower()} me with'
                                              f' {player.name.lower()}`', colour=0xf7b731)
        else:
            embed = discord.Embed(title='You Lose!',
                                  description=f'`I chose {choice.name.lower()} and have'
                                              f' {RPSLS(int(f"{choice.value}{player.value}")).name.lower()} your'
                                              f' {player.name.lower()}`', colour=0xff6961)

        await ctx.send(embed=embed)
