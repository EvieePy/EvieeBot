import discord
from discord.ext import commands

import utils


class Pythonista(metaclass=utils.MetaCog):

    def __init__(self, bot):
        self.bot = bot
        self.guild_id = 490948346773635102
        self.channel = self.bot.get_channel(491097233765433346)

    async def on_member_join(self, member):
        if member.guild.id != self.guild_id:
            return

        channel = self.bot.get_channel(491097233765433346)
        await channel.send(f'**+** | {str(member)}({"User" if not member.bot else "Bot"})')

    async def on_member_remove(self, member):
        if member.guild.id != self.guild_id:
            return

        channel = self.bot.get_channel(491097233765433346)
        await channel.send(f'**-** | {str(member)}({"User" if not member.bot else "Bot"})')

    @commands.command(hidden=True)
    async def twitchio(self, ctx):
        role = discord.utils.get(ctx.guild.roles, name='TwitchIO')

        if role in ctx.author.roles:
            await ctx.author.remove_roles(role, reason='Automatic role command.')
            await ctx.message.add_reaction('\U0001F494')
        else:
            await ctx.author.add_roles(role, reason='Automatic role command.')
            await ctx.message.add_reaction('❤')
