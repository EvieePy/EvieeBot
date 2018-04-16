import discord
from discord.ext import commands

import asyncio
import enum
import io
import random
from functools import partial
from PIL import Image, ImageSequence, ImageFont, ImageDraw, ImageColor

import utils


class Misc(metaclass=utils.MetaCog, category='Misc', colour=0xa5d8d8, thumbnail='https://i.imgur.com/WGjcdqg.png'):
    """Miscellaneous commands which don't really have a place in this life... What am I even doing with mine!?
     I need a tequila.
     """

    __slots__ = ('bot', )

    def __init__(self, bot):
        self.bot = bot

    async def __error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f'You are only permitted to one Channel per 15m.\n```css\n'
                           f'Your cooldown expires in: [{error.retry_after / 60} minutes.]\n```')

    async def __local_check(self, ctx):
        if not ctx.guild:
            await ctx.send('You are not able to use this command in Private Messages.')
            return False

        return True

    @property
    def fb_chan(self):
        return self.bot.get_channel(352013640691351552)

    @property
    def hellos(self):
        return 'Hello', 'Hi', 'Hey', 'Heya', 'Heyo', 'Hai', 'Howdy!', "G'Day!", 'Hey there', 'Hai there', 'Hola'

    @commands.command(name='emojis', aliases=['emotes'], cls=utils.EvieeCommandGroup)
    async def emojis_(self, ctx, *, name: str=None):
        """Display all emojis in a paginated embed.

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
        embed = discord.Embed(title=emoji.name, colour=0xEEEE00)
        embed.add_field(name='Guild', value=f'`{emoji.guild.name} (ID: {emoji.guild.id})`')
        embed.add_field(name='URL', value=f'[Open]({emoji.url})')
        embed.set_thumbnail(url=emoji.url)

        await ctx.paginate(extras=[embed], )

    @commands.command(name='hi', clas=utils.EvieeCommand)
    async def hello(self, ctx):
        """Say hello to Eviee."""
        await ctx.send(f'{random.choice(self.hellos)} {ctx.author.display_name}! <:3cc:431696022461349888>')

    async def auto_room(self):
        pass

    @commands.command(name='temp', aliases=['temp_channel'], cls=utils.EvieeCommand)
    @commands.cooldown(1, 900, commands.BucketType.user)
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
            cat = discord.utils.get(ctx.guild.categories, name='TEMP CHANNELS')
            if not cat:
                cat = await ctx.guild.create_category(name='TEMP CHANNELS')

            chan = await ctx.guild.create_voice_channel(name=name,
                                                        overwrites={
                                                            ctx.author: discord.PermissionOverwrite(mute_members=True,
                                                                                                    deafen_members=True,
                                                                                                    connect=True,
                                                                                                    speak=True,
                                                                                                    move_members=True,
                                                                                                    manage_channels=True,
                                                                                                    manage_roles=True,
                                                                                                    ),
                                                            ctx.guild.default_role: discord.PermissionOverwrite(
                                                                speak=False,
                                                                connect=True
                                                            )},
                                                        category=cat,
                                                        reason='Temp Channel.')
        except discord.HTTPException:
            return await ctx.send('Something went wrong while trying to create your channel.'
                                  ' Perhaps I do not have the correct permissions.')

        await ctx.send(f'**Your channel has been created.**\nOther members may now join **`{chan}`**\n'
                       f'```ini\nYour channel will be destroyed shortly after the channel becomes empty.\n'
                       f'You may change permissions, channel name and more while the channel is active.\n'
                       f'By Default, `@everyone` are unable to speak.```',
                       delete_after=30)

        while not self.bot.is_closed():
            await asyncio.sleep(120)

            if len(chan.members) == 0:
                await chan.delete(reason='Temp Channel: Empty for too long.')

    @commands.command(name='feedback', aliases=['fb', 'suggest'], cls=utils.EvieeCommand)
    @commands.cooldown(2, 900, commands.BucketType.user)
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
        if not feedback:
            return await ctx.send("You haven't left any feedback. Try again!")
        if len(feedback) > 1024:
            return await ctx.send('Feedback can not be longer than 1024 characters.')

        embed = discord.Embed(title=f'Feedback',
                              description=f'```ini\n'
                                          f'Guild: {ctx.guild}(ID: {ctx.guild.id})\n'
                                          f'User : {ctx.author}(ID: {ctx.author.id})\n```',
                              colour=0xff69b4)
        embed.add_field(name='Message', value=feedback)
        await self.fb_chan.send(embed=embed)

        await ctx.send(f'Thanks {ctx.author.display_name}. Your feedback has been received.', delete_after=20)

    @commands.command(name='invite')
    async def get_invite(self, ctx):
        """Invite Eviee to your guild!"""

        # TODO Change IDs
        embed = discord.Embed(colour=0xff69b4, title='Invite Eviee')
        embed.add_field(name='With Permissions', value=
                        '[Click Me!](https://discordapp.com/oauth2/authorize?client_id=319047630048985099&scope=bot'
                        '&permissions=389409878)')
        embed.add_field(name='Without Permissions', value=
                        '[Click Me!](https://discordapp.com/oauth2/authorize?client_id=319047630048985099&scope=bot'
                        '&permissions=0)')
        await ctx.send(embed=embed)


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
        base = Image.open('resources/hug.gif')
        font = ImageFont.truetype('resources/fonts/Playtime.ttf', 12)

        hugbase = 45

        invalid = (6, 8, 9, 10, 11)
        values = {12: 45, 14: 10, 17: 5, 20: 5, 23: 5}

        frames = []

        def generate():
            for index, frame in enumerate(ImageSequence.Iterator(base)):
                draw = ImageDraw.Draw(frame)

                if index in invalid:
                    pass
                else:
                    hugbase += values.get(index, 15)

                draw.text((hugbase, 115), f'{a.display_name}', font=font, fill=self.hug_colour)
                draw.text((170, 250), f'{b.display_name}', font=font, fill=self.hug_colour)

                frames.append(frame.copy())

        await self.bot.loop.run_in_executor(None, generate)

        f = io.BytesIO()
        frames[0].save(f, 'gif', save_all=True, duration=0, loop=0, append_images=frames[1:])
        f.seek(0)
        base.close()

        return discord.File(f, f'{a.id}{b.id}_hug.gif')

    async def make_bn(self, user, msg: str):
        base = Image.open('resources/bn.gif')
        font = ImageFont.truetype('resources/fonts/Playtime.ttf', 16)

        msg = ' '.join(msg.split())
        w, h = font.getsize(msg)

        frames = []

        def generate():
            for index, frame in enumerate(ImageSequence.Iterator(base)):
                if index >= 7:
                    draw = ImageDraw.Draw(frame)
                    draw.fontmode = '1'
                    draw.text(((500 - w) / 2, (285 - h) / 2), msg, font=font, align='center', fill=99)

                frames.append(frame.copy())

        await self.bot.loop.run_in_executor(None, generate)

        last_frame = frames[-1]

        for x in range(25):
            frames.append(last_frame.copy())

        f = io.BytesIO()
        frames[0].save(f, 'gif', save_all=True, duration=0.1, loop=0, append_images=frames[1:])
        f.seek(0)
        base.close()

        return discord.File(f, f'{user.id}_bn.gif')

    async def make_lick2(self, a, b):
        base = Image.open('resources/lick2.gif')
        font = ImageFont.truetype('resources/fonts/Playtime.ttf', 30)

        aw, ah = font.getsize(a.display_name)
        bw, bh = font.getsize(b.display_name)

        frames = []

        def generate():
            for index, frame in enumerate(ImageSequence.Iterator(base)):
                draw = ImageDraw.Draw(frame)
                draw.text(((420 - bw) / 2, 400), b.display_name, font=font, fill=self.hug_colour)
                draw.text(((730 - aw) / 2, 60), a.display_name, font=font, fill=99)

                frames.append(frame.copy())

        await self.bot.loop.run_in_executor(None, generate)

        f = io.BytesIO()
        frames[0].save(f, 'gif', save_all=True, duration=0.1, loop=0, append_images=frames[1:])
        f.seek(0)
        base.close()

        return discord.File(f, f'{a.id}{b.id}_licks2.gif')

    async def make_lick(self, a, b):
        base = Image.open('resources/lick.gif')
        font = ImageFont.truetype('resources/fonts/Playtime.ttf', 30)

        aw, ah = font.getsize(a.display_name)
        bw, bh = font.getsize(b.display_name)

        frames = []

        def generate():
            for index, frame in enumerate(ImageSequence.Iterator(base)):
                draw = ImageDraw.Draw(frame)
                draw.text(((500 - bw) / 2, 450), b.display_name, font=font, fill=self.hug_colour)

                if index >= 60 or index <= 8:
                    pass
                else:
                    draw.text(((450 - aw) / 2, 150), a.display_name, font=font, align='center', fill=99)
                    # draw.text(((500 - w) / 2, (285 - h) / 2), msg, font=font, align='center', fill=99)

                frames.append(frame.copy())

        await self.bot.loop.run_in_executor(None, generate)
        last_frame = frames[-1]

        for x in range(25):
            frames.append(last_frame.copy())

        f = io.BytesIO()
        frames[0].save(f, 'gif', save_all=True, duration=0.1, loop=0, append_images=frames[1:])
        f.seek(0)
        base.close()

        return discord.File(f, f'{a.id}{b.id}_lick.gif')

    async def make_hearts(self, a, b):
        base = Image.open('resources/heart.gif')
        font = ImageFont.truetype('resources/fonts/Playtime.ttf', 20)

        aw, ah = font.getsize(a.display_name)
        bw, bh = font.getsize(b.display_name)

        frames = []

        def generate():
            for index, frame in enumerate(ImageSequence.Iterator(base)):
                draw = ImageDraw.Draw(frame)
                draw.text(((270 - bw) / 2, 70), b.display_name, font=font, fill=self.hug_colour)
                draw.text(((730 - aw) / 2, 70), a.display_name, font=font, fill=99)

                frames.append(frame.copy())

        await self.bot.loop.run_in_executor(None, generate)

        f = io.BytesIO()
        frames[0].save(f, 'gif', save_all=True, duration=0.1, loop=0, append_images=frames[1:])
        f.seek(0)
        base.close()

        return discord.File(f, f'{a.id}{b.id}_hearts.gif')

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
