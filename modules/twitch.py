import discord
from discord.ext import commands
from twitchio import commands as tcommands

import asyncio

import utils


class Twitch(tcommands.TwitchBot, metaclass=utils.MetaCog):

    def __init__(self, bot):
        self.dbot = bot
        super().__init__(irc_token='oauth:aw55sstdy8udfbtxjgdktocdn6mlyn', api_token='test', nick='mysterialpy',
                         prefix='?', channels=['mysterialpy'])

        self.loop.create_task(self.start())
        self.loop.create_task(self.discord_relay())

        self.channel = None
        self.author = None

    async def discord_relay(self):
        await self.dbot.wait_until_ready()

        def check(message):
            return message.author.id == self.dbot.user.id and message.channel.id == self.channel.id

        while True:
            message = await self.dbot.wait_for('message', check=check)

            message.author = message.guild.get_member(402159684724719617)
            ctx = await self.dbot.get_context(message, cls=utils.EvieeContext)
            await self.dbot.invoke(ctx)

    async def on_ready(self):
        self.channel = self.dbot.get_channel(490950849867284480)

    @tcommands.twitch_command(name='test')
    async def test(self, ctx):
        await ctx.send(f'Hello {ctx.author.name}')

    @tcommands.twitch_command(name='points')
    async def twitch_points(self, ctx):
        async with self.dbot.pool.acquire() as conn:
            value = await conn.fetchval("""SELECT points FROM twitch
                                           WHERE username = $1 AND channel = $2""", ctx.author.name, ctx.channel.name)

        if not value:
            return await ctx.send(f'{ctx.author.name} has no points!')

        await ctx.send(f'{ctx.author.name} has {value} points!')

    async def event_ready(self):
        print(f'Twitch Bot Ready | {self.nick}')

    async def event_message(self, message):
        await self.channel.send(message.content)

        async with self.dbot.pool.acquire() as conn:
            await conn.execute("""INSERT INTO twitch(username, channel, points) VALUES($1, $2, 1)
                                  ON CONFLICT (username, "channel")
                                  DO UPDATE SET points = COALESCE(twitch.points, 0)::int + 1""",
                               message.author.name, message.channel.name)

        await self.process_commands(message)

    async def on_message(self, message):
        pass
