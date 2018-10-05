import discord
from discord.ext import commands

import utils


class TwitchCog(metaclass=utils.MetaCog, colour=0x6441a5,
                thumbnail='https://www.twitch.tv/p/assets/uploads/glitch_474x356.png'):
    """Twitch related commands. This module is just a prototype for now!"""

    BASE = 'https://api.twitch.tv/helix/webhooks/hub?'
    HOST = '192.168.1.43'
    PORT = 6968

    def __init__(self, bot):
        self.bot = bot

    async def __error(self, ctx, error):
        if isinstance(error, commands.BotMissingPermissions):
            return await ctx.send(f'I am missing permissions to run this command! I require `{error.missing_perms}`.')

    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if not after.activity:
            return
        elif isinstance(before.activity, discord.Streaming):
            return
        elif not isinstance(after.activity, discord.Streaming):
            return

        async with self.bot.pool.acquire() as conn:
            data = await conn.fetchval("""SELECT twitch FROM guilds WHERE id = $1""", before.guild.id)

        if not data:
            return

        channel = self.bot.get_channel(data)
        if not channel:
            return

        embed = discord.Embed(title=f'{after.activity.name}', description=f'Watch live: {after.activity.url}')
        embed.add_field(name='Game', value=after.activity.details)
        embed.set_author(name=f'{after.display_name}({after.activity.twitch_name})', url=after.activity.url,
                         icon_url=after.avatar_url)
        embed.set_thumbnail(url=after.avatar_url)

        role = discord.utils.get(after.guild.roles, name='Stream Announcements')
        await channel.send(content=f'{role.mention}', embed=embed)

    @commands.command(cls=utils.EvieeCommandGroup)
    async def twitch(self, ctx):
        pass

    @twitch.command(name='channel', aliases=['announcements', 'announce'])
    @commands.bot_has_permissions(manage_roles=True)
    async def twitch_channel(self, ctx, *, channel: discord.TextChannel=None):
        """Set your Twitch announcements channel.

        Parameters
        ------------
        channel: [Optional]
            The channel to set as your announcement channel. If this is none the channel you run this command
            will be used.
        """
        if channel is None:
            channel = ctx.channel

        async with self.bot.pool.acquire() as conn:
            await conn.execute("""UPDATE guilds SET twitch = $1 WHERE guilds.id = $2""", channel.id, ctx.guild.id)

        role = discord.utils.get(ctx.guild.roles, name='Stream Announcements')
        if not role:
            await ctx.guild.create_role(name='Stream Announcements', mentionable=True,
                                        reason='Stream announcement channel setup')

        await ctx.send(f'Your Twitch announcement channel has been set to: {channel.mention}.'
                       f' Users may also subscribe to announcements to receive notifications with'
                       f' `{ctx.prefix}twitch subscribe`')

    @twitch.command(name='subscribe', aliases=['sub'])
    @commands.bot_has_permissions(manage_roles=True)
    async def twitch_subscribe(self, ctx):
        async with self.bot.pool.acquire() as conn:
            data = await conn.fetchval("""SELECT twitch FROM guilds WHERE id = $1""", ctx.guild.id)

            if not data:
                return await ctx.send('Your twitch announcement channel has not been setup yet.\n'
                                      'Please run: `twitch channel` in your desired announcement channel.')

        role = discord.utils.get(ctx.guild.roles, name='Stream Announcements')
        await ctx.author.add_roles(role, reason='Stream Announcements')

        await ctx.send(f'Alright {ctx.author.mention}, I have given you the Stream Announcement role.')

    @twitch.command(name='setup')
    async def twitch_setup(self, ctx, *, channel: str):
        """Setup your Twitch channel for announcements.
        """
        async with self.bot.pool.acquire() as conn:
            data = await conn.fetchval("""SELECT twitch FROM guilds WHERE id = $1""", ctx.guild.id)

            if not data:
                return await ctx.send('Your twitch announcement channel has not been setup yet.\n'
                                      'Please run: `twitch channel` in your desired announcement channel.')

            await conn.execute("""INSERT INTO twitch(uid, channel) VALUES($1, $2)
                                  ON CONFLICT(uid) DO UPDATE SET channel = $2""", ctx.author.id, channel)

        await ctx.send(f'Thanks. Your Twitch channel has been set to: `{channel}`')
