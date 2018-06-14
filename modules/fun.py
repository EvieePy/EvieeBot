import discord
from discord.ext import commands

import asyncio
import enum
import io
import numpy
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

    @commands.command(name='markov', cls=utils.EvieeCommand)
    async def do_markov(self, ctx, *, channel: discord.TextChannel=None):
        """Generate so babble using a markov chain.

        Parameters
        ------------
        channel: Optional
            The text channel to generate text from. This must be a channel I can read.
            If not provided, defaults to current channel.

        Examples
        ----------
        <prefix>markov
        <prefix>markov <channel>

            {ctx.prefix}markov #testing
        """
        if not channel:
            channel = ctx.channel

        msg = await ctx.send('Attempting to generate Markov...')

        chain = {}
        try:
            data = ' '.join([m.clean_content for m in await channel.history(limit=1000).flatten()
                             if not m.author.bot]).replace('\n\n', ' ').split(' ')
        except discord.HTTPException:
            return await msg.edit(content='Could not access destination provided.')

        if len(data) < 50:
            return await msg.edit(content='Not enough data to create Markov.')

        index = 1
        for word in data[index:]:
            key = data[index - 1]
            if key in chain:
                chain[key].append(word)
            else:
                chain[key] = [word]
            index += 1

        word1 = random.choice(list(chain.keys()))
        message = word1.capitalize()

        while len(message.split(' ')) < 12:
            word2 = random.choice(chain[word1])
            word1 = word2
            message += ' ' + word2

        await msg.edit(content=message)


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
    __slots__ = ('bot', 'c4')

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.c4 = []

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

    @commands.command(name='connect4', aliases=['c4'])
    async def connect_four(self, ctx):
        """Play a game of Connect Four."""
        if ctx.channel.id in self.c4:
            return await ctx.send('There is already a Connect Four game in this channel. Please wait for it to finish.')

        joiner = discord.Embed(description=f'{ctx.author.display_name} wants to play Connect Four!\n\n'
                                           f'React with ☑ to join!')
        joiner.set_footer(text='This will be valid for 5 minutes.')
        joiner.set_thumbnail(url='https://i.imgur.com/BF6KD1E.png')

        msg = await ctx.send(embed=joiner)
        try:
            await msg.add_reaction('☑')
        except discord.HTTPException:
            pass

        try:
            user = await self.c4join_loop(ctx)
        except asyncio.TimeoutError:
            return await ctx.send(f'{ctx.author.mention}. No one joined within 5 minutes, please try again!',
                                  delete_after=30)
        finally:
            await msg.delete()

        self.c4.append(ctx.channel.id)
        c4 = ConnectFour(ctx.author, user)

        embed = c4.generate_board()
        board = await ctx.send(embed=embed)

        self.bot.loop.create_task(c4.play_loop(ctx, board))

    async def c4join_loop(self, ctx: utils.EvieeContext):
        def check(r, u):
            if u == ctx.me:
                return False
            return str(r) == '☑'

        while True:
            react, user = await self.bot.wait_for('reaction_add', check=check, timeout=300)

            return user


class ConnectFour:

    __slots__ = ('FIELD', 'board', 'new', 'numbers', 'end', 'player_one', 'player_two', 'top', 'turn')

    ROWS = 6
    COLS = 7

    def __init__(self, one: discord.Member, two: discord.Member):
        self.FIELD = [['⚫' for _ in range(7)] for _ in range(6)]
        self.board = None
        self.new = False
        self.numbers = [f'{n}\u20E3' for n in range(1, 8)]
        self.end = False
        self.top = 5
        self.player_one = (one, '🔴')
        self.player_two = (two, '🔵')

        self.turn = 0

    def is_valid(self, c):
            return self.FIELD[self.top][c] == '⚫'

    def next_open(self, c):
        for r in range(self.ROWS):
            if self.FIELD[r][c] == '⚫':
                return r

    def make_move(self, r, c, player):
        self.FIELD[r][c] = player[1]

    def check_win(self, player):
        for c in range(self.COLS - 3):
            for r in range(self.ROWS):
                if self.FIELD[r][c] == player[1] and\
                        self.FIELD[r][c + 1] == player[1] and\
                        self.FIELD[r][c + 2] == player[1] and\
                        self.FIELD[r][c + 3] == player[1]:
                    return True

        for c in range(self.COLS):
            for r in range(self.ROWS - 3):
                if self.FIELD[r][c] == player[1] and\
                        self.FIELD[r + 1][c] == player[1] and\
                        self.FIELD[r + 2][c] == player[1] and\
                        self.FIELD[r + 3][c] == player[1]:
                    return True

        for c in range(self.COLS - 3):
            for r in range(self.ROWS - 3):
                if self.FIELD[r][c] == player[1] and\
                        self.FIELD[r + 1][c + 1] == player[1] and\
                        self.FIELD[r + 2][c + 2] == player[1] and \
                        self.FIELD[r + 3][c + 3] == player[1]:
                    return True

        for c in range(self.COLS - 3):
            for r in range(3, self.ROWS):
                if self.FIELD[r][c] == player[1] and\
                        self.FIELD[r - 1][c + 1] == player[1] and\
                        self.FIELD[r - 2][c + 2] == player[1] and \
                        self.FIELD[r - 3][c + 3] == player[1]:
                    return True

    def generate_field(self):
        fields = []

        for _ in self.FIELD:
            line = ''.join(str(e) for e in _)
            fields.append(line)

        fields.append(''.join(self.numbers))
        fields = numpy.flip(fields, 0)

        field = '\n'.join(line for line in fields)
        return field

    def generate_board(self):
        field = self.generate_field()
        embed = discord.Embed(description=field, colour=0x36393E)
        embed.set_footer(text='Enter your number to make a move.')

        if self.current_player() == 0:
            embed.add_field(name='\u200b', value=f'{self.player_one[1]} = {self.player_one[0].display_name} <---\n'
                                                 f'{self.player_two[1]} = {self.player_two[0].display_name}')
            embed.set_thumbnail(url=self.player_one[0].avatar_url)
        else:
            embed.add_field(name='\u200b', value=f'{self.player_one[1]} = {self.player_one[0].display_name}\n'
                                                 f'{self.player_two[1]} = {self.player_two[0].display_name} <---')
            embed.set_thumbnail(url=self.player_two[0].avatar_url)

        return embed

    def generate_winner(self, winner):
        field = self.generate_field()
        embed = discord.Embed(title=f'{winner[0].display_name} Wins!', description=field, colour=0x36393E)

        if winner == self.player_one:
            embed.add_field(name='\u200b', value=f'{self.player_one[1]} = **{self.player_one[0].display_name}** (Wins)\n'
                                                 f'{self.player_two[1]} = {self.player_two[0].display_name}'
                                                 f'\n\n'
                                                 f'**{winner[0].display_name}** won the game in **{self.turn}** turns.')
            embed.set_thumbnail(url=winner[0].avatar_url)
        else:
            embed.add_field(name='\u200b', value=f'{self.player_one[1]} = {self.player_one[0].display_name}\n'
                                                 f'{self.player_two[1]} = **{self.player_two[0].display_name}** (Wins)'
                                                 f'\n\n'
                                                 f'**{winner[0].display_name}** won the game in **{self.turn}** turns.')
            embed.set_thumbnail(url=winner[0].avatar_url)

        return embed

    def generate_draw(self):
        field = self.generate_field()
        embed = discord.Embed(title=f'Draw!', description=field, colour=0x36393E)

        embed.add_field(name='\u200b', value=f'{self.player_one[1]} = {self.player_one[0].display_name}\n'
                                             f'{self.player_two[1]} = {self.player_two[0].display_name}'
                                             f'\n\n'
                                             f'**The game has ended in a Draw!**')
        embed.set_thumbnail(url='https://i.imgur.com/BF6KD1E.png')

        return embed

    def current_player(self):
        return self.turn % 2

    async def play_loop(self, ctx, board):
        self.board = board
        cog = ctx.bot.get_cog('Games')

        def check(msg):
            if self.current_player() == 0:
                return self.player_one[0] == msg.author
            else:
                return self.player_two[0] == msg.author

        while True:
            if self.current_player() == 0:
                player = self.player_one
                opposite = self.player_two
            else:
                player = self.player_two
                opposite = self.player_one

            try:
                message = await ctx.bot.wait_for('message', check=check, timeout=180)
            except asyncio.TimeoutError:
                cog.c4.remove(ctx.channel.id)

                await self.board.delete()
                await ctx.send(embed=self.generate_winner(opposite))
                return await ctx.send(f'{player[0].mention} has taken too long to move.'
                                      f' {opposite[0].mention} wins by default.')

            if any(n == message.content for n in ['quit', 'end', 'die', 'ff', 'surrender']):
                await self.board.delete()
                await ctx.send(embed=self.generate_winner(opposite))
                return await ctx.send(f'{player[0].mention} has quit the game. {opposite[0].mention} wins by default.')

            try:
                move = int(message.content)
            except ValueError:
                continue
            if move < 1 or move > 7:
                continue

            try:
                await message.delete()
            except discord.HTTPException:
                pass

            # Align with the board. Index 0
            move -= 1

            if not self.is_valid(move):
                await ctx.send('Invalid move!')
                continue

            self.turn += 1

            if self.turn == 42:
                cog.c4.remove(ctx.channel.id)
                if not self.check_win(player):
                    await self.board.delete()
                    return await ctx.send(embed=self.generate_draw())

            row = self.next_open(move)
            self.make_move(row, move, player)

            if not await self.is_current_fresh(ctx.channel, 6):
                await self.board.delete()
                self.new = True

            if self.check_win(player):
                cog.c4.remove(ctx.channel.id)

                if self.new:
                    return await ctx.send(embed=self.generate_winner(player))
                return await self.board.edit(embed=self.generate_winner(player))

            if self.new:
                self.board = await ctx.send(embed=self.generate_board())
                self.new = False
            else:
                await self.board.edit(embed=self.generate_board())
    
    async def is_current_fresh(self, chan, limit):
        try:
            async for m in chan.history(limit=limit):
                if m.id == self.board.id:
                    return True
        except (discord.HTTPException, AttributeError):
            return False
        return False


class TicTacToe:

    __slots__ = ()

    def __init__(self):
        pass
