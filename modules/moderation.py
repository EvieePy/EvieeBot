import discord
from discord.ext import commands

import utils


class Moderation(metaclass=utils.MetaCog, colour=0xffd0b5, thumbnail='https://i.imgur.com/QJiga6E.png'):
    """Nothing like a good spanking! These commands should give your mods a good feeling inside.
    Most of these commands require, [Manage Sever] permissions.
    """

    def __init__(self, bot):
        self.bot = bot

    async def __local_check(self, ctx):
        if not ctx.guild:
            raise commands.NoPrivateMessage

        return True

    async def __error(self, ctx, error):
        if isinstance(error, commands.NoPrivateMessage):
            try:
                await ctx.send('This command can not be used in DMs.')
            except discord.HTTPException:
                pass

        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f'`{error.param.name}` is a required argument which is missing.')

    @commands.command(name='prefix', cls=utils.AbstractorGroup, abstractors=['add', 'remove', 'list'])
    async def prefix(self, ctx):
        """Prefix related commands.

        <This Group implements Base Commands>
        !Base commands are also sub commands!

        Base Commands
        ---------------
            add
            remove
            list

        Examples
        ----------
        <prefix>prefix add <custom_prefix>
        <prefix>remove prefix <custom_prefix>

            {ctx.prefix}prefix list
            {ctx.prefix}prefix remove "eviee pls "
        """

    @prefix.command(name='add')
    @commands.has_permissions(manage_guild=True)
    async def add_prefix(self, ctx, *, prefix: str):
        """Assign a Prefix to Eviee for use in your guild.

        Examples
        ----------
        <prefix>prefix add <custom_prefix>
        <prefix>add prefix <custom_prefix>

            {ctx.prefix}add prefix "eviee pls "
            {ctx.prefix}prefix add ?!
        """
        lru = self.bot.lru_prefix[ctx.guild.id]

        prefix = prefix.strip('"').strip("'")

        if len(prefix) > 50:
            return await ctx.error(info='The prefix can not be over 50 characters long. Please try again.')
        if prefix in lru:
            return await ctx.error(info=f'`"{prefix}"` is already an assigned prefix.')

        async with self.bot.pool.acquire() as conn:
            await conn.execute("""UPDATE guilds SET prefixes = prefixes || $1::text WHERE id IN ($2)""",
                               prefix, ctx.guild.id)

        lru.append(prefix)
        await ctx.send(f'The prefix `"{prefix}"` has successfully been added.')

    @prefix.command(name='remove')
    async def remove_prefix(self, ctx, *, prefix: str):
        """Remove a Prefix from Eviee currently being used in your guild.

        Examples
        ----------
        <prefix>prefix remove <custom_prefix>
        <prefix>remove prefix <custom_prefix>

            {ctx.prefix}remove prefix "eviee pls "
            {ctx.prefix}prefix remove ?!
        """
        lru = self.bot.lru_prefix[ctx.guild.id]

        prefix = prefix.strip('"').strip("'")

        if prefix not in lru:
            return await ctx.error(info=f'`"{prefix}"` is not currently assigned to me.')

        lru.remove(prefix)
        await self.bot.pool.execute("""UPDATE guilds SET prefixes = array_remove(prefixes, $1::text) WHERE id IN ($2)""",
                                    prefix, ctx.guild.id)

        await ctx.send(f'Successfully removed `"{prefix}"` from my assigned prefixes.')

    @prefix.command(name='list')
    async def list_prefix(self, ctx):
        """List the available prefixes for your guild.

        Examples
        ----------
        <prefix>prefix list
        <prefix>list prefix

            {ctx.prefix}prefix list
            {ctx.prefix}list prefix
        """
        await ctx.paginate(title=f'Prefixes for {ctx.guild.name}', entries=self.bot.lru_prefix[ctx.guild.id],
                           fmt='`"', footer='You may also mention me.')

    @commands.command(name='prefixes', cls=utils.EvieeCommand)
    async def _prefixes(self, ctx):
        """An alias to `prefix list`.

        Examples
        ----------
        <prefix>prefixes

            {ctx.prefix}prefixes
        """
        await ctx.paginate(title=f'Prefixes for {ctx.guild.name}', entries=self.bot.lru_prefix[ctx.guild.id],
                           fmt='`"', footer='You may also mention me.')
