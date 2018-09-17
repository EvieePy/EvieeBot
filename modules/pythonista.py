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

        await self.channel.send(f'**+** | {str(member)}({"User" if not member.bot else "Bot"})')

    async def on_member_leave(self, member):
        if member.guild.id != self.guild_id:
            return

        await self.channel.send(f'**-** | {str(member)}({"User" if not member.bot else "Bot"})')

