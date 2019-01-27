import discord
from discord.ext import commands
import bs4

import utils


class Pythonista(metaclass=utils.MetaCog):

    def __init__(self, bot):
        self.bot = bot
        self.guild_id = 490948346773635102
        self.channel = self.bot.get_channel(491097233765433346)
        self.rtfm_cache = {}

        self.raid = False

        self.bot.loop.create_task(self.build_rtfm_cache())

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

    @commands.command(aliases=['rtfd'])
    async def rtfm(self, ctx, *, lookup: str):

        matches = utils.fuzzyfinder(lookup, [(a, v) for a, v in self.rtfm_cache.items()], key=lambda t: t[1], lazy=False)[:5]
        embed = discord.Embed(title='TwitchIO - RTFD')

        if not matches:
            embed.description = f'Sorry no results were found for `{lookup}`. Try being more specific.\n' \
                                f'https://twitchio.readthedocs.io/en/rewrite/twitchio.html'
            return await ctx.send(embed=embed)

        entries = []
        for m in matches:
            entry = f'[{m[0]}]({m[1]})'
            entries.append(entry)

        entries = '\n'.join(entries)
        embed.description = entries

        await ctx.send(embed=embed)

    async def build_rtfm_cache(self):
        self.rtfm_cache = {}

        base = 'https://twitchio.readthedocs.io/en/rewrite/twitchio.html'
        basecom = 'https://twitchio.readthedocs.io/en/rewrite/twitchio.commands.html'

        async with self.bot.session.get(base) as resp:
            data = await resp.text()

        async with self.bot.session.get(basecom) as resp:
            commands = await resp.text()

        soup = bs4.BeautifulSoup(data, 'html.parser')

        for a in soup.find_all('a', {'class': 'headerlink'}):
            self.rtfm_cache[a['href'].replace('#twitchio.', '')] = base + a['href']

        soup = bs4.BeautifulSoup(commands, 'html.parser')

        for a in soup.find_all('a', {'class': 'headerlink'}):
            self.rtfm_cache[a['href'].replace('#twitchio.ext.commands.', '')] = basecom + a['href']

    @commands.group(name='raid', hidden=True, invoke_without_command=True)
    @commands.has_role('Mod')
    async def raid_(self, ctx):
        if self.raid:
            await ctx.send('Raid Mode: ON')
        else:
            await ctx.send('Raid Mode: Off')

    @raid_.command(name='on', hidden=True)
    async def raid_on(self, ctx):
        for member in ctx.guild.members:
            await member.add_roles(discord.utils.get(ctx.guild.roles, name='muted'))

        self.raid = True
        await ctx.send('Raid Mode: On')

    @raid_.command(name='off', hidden=True)
    async def raid_off(self, ctx):
        for member in ctx.guild.members:
            await member.remove_roles(discord.utils.get(ctx.guild.roles, name='muted'))

        self.raid = False
        await ctx.send('Raid Mode: Off')








